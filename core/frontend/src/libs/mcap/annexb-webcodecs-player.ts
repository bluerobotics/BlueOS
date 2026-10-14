/**
 * Live Annex-B video through WebCodecs onto a canvas.
 *
 * This is the low-latency path: no fMP4, no MSE, no `<video>` preroll. It only exists in a secure
 * context (HTTPS or localhost). Plain HTTP BlueOS still uses the MSE player.
 *
 * Prefer Annex-B without an avcC/hvcC description (the live packets already look like that). If the
 * decoder rejects it, retry with a decoder configuration record and length-prefixed NALs.
 */
import {
  extractAvcDecoderConfigurationRecord,
  extractHevcDecoderConfigurationRecord,
  serializeAvcDecoderConfigurationRecord,
  serializeHevcDecoderConfigurationRecord,
} from 'mediabunny/codec-data'

import type { AnnexBMsePlayerOptions } from './annexb-player'
import { annexBToLengthPrefixed, isKeyframe, ParameterSetCache, VideoFormat } from './codec'
import { probeDecoderInfo, VideoDecoderInfo } from './mux'

const MAX_DECODE_QUEUE = 2

export function isWebCodecsSupported(): boolean {
  return typeof VideoDecoder === 'function'
}

export class AnnexBWebCodecsPlayer {
  private decoder: VideoDecoder | null = null

  private decoderInfo: VideoDecoderInfo | null = null

  private parameterSets = new ParameterSetCache()

  private context: CanvasRenderingContext2D | null = null

  private destroyed = false

  private ready = false

  private needsKeyframe = true

  private usedDescription = false

  constructor(
    private canvas: HTMLCanvasElement,
    private options: AnnexBMsePlayerOptions = {},
  ) {}

  push(data: Uint8Array, format: VideoFormat, _timestampSeconds?: number): void {
    if (this.destroyed || data.length === 0) {
      return
    }
    const annexB = this.parameterSets.withParameterSets(data, format)
    if (annexB.length === 0) {
      return
    }
    const keyframe = isKeyframe(annexB, format)
    if (this.needsKeyframe && !keyframe) {
      return
    }
    if (!this.decoder) {
      if (!keyframe) {
        return
      }
      try {
        this.openDecoder(probeDecoderInfo(format, annexB), annexB, false)
      } catch (error) {
        this.reportError(error)
        return
      }
    }
    if (!this.decoder || this.decoder.state !== 'configured') {
      return
    }
    if (!keyframe && this.decoder.decodeQueueSize >= MAX_DECODE_QUEUE) {
      this.needsKeyframe = true
      return
    }
    this.decodeChunk(annexB, keyframe)
  }

  destroy(): void {
    this.destroyed = true
    this.closeDecoder()
  }

  private openDecoder(decoderInfo: VideoDecoderInfo, keyframe: Uint8Array, withDescription: boolean): void {
    this.decoderInfo = decoderInfo
    this.usedDescription = withDescription
    this.closeDecoder()
    const decoder = new VideoDecoder({
      output: (frame) => {
        if (this.decoder !== decoder) {
          frame.close()
          return
        }
        this.paint(frame)
      },
      error: (error) => {
        if (this.destroyed || this.decoder !== decoder) {
          return
        }
        this.onDecoderError(error, decoderInfo, keyframe)
      },
    })
    const config: VideoDecoderConfig = {
      codec: decoderInfo.codec,
      codedWidth: decoderInfo.width,
      codedHeight: decoderInfo.height,
      optimizeForLatency: true,
    }
    if (withDescription) {
      config.description = decoderDescription(decoderInfo.format, keyframe)
    }
    decoder.configure(config)
    this.decoder = decoder
  }

  private onDecoderError(error: DOMException, decoderInfo: VideoDecoderInfo, keyframe: Uint8Array): void {
    if (!this.usedDescription) {
      try {
        this.openDecoder(decoderInfo, keyframe, true)
        this.decodeChunk(keyframe, true)
        return
      } catch (retryError) {
        this.reportError(retryError)
        return
      }
    }
    this.reportError(error)
  }

  private decodeChunk(annexB: Uint8Array, keyframe: boolean): void {
    if (!this.decoder || this.decoder.state !== 'configured') {
      return
    }
    const queuedAt = performance.now() / 1000
    const data = this.usedDescription ? annexBToLengthPrefixed(annexB, this.decoderInfo?.format ?? 'h264') : annexB
    try {
      this.decoder.decode(new EncodedVideoChunk({
        type: keyframe ? 'key' : 'delta',
        timestamp: Math.round(queuedAt * 1e6),
        data,
      }))
      this.needsKeyframe = false
    } catch (error) {
      this.needsKeyframe = true
      this.reportError(error)
    }
  }

  private closeDecoder(): void {
    const decoder = this.decoder
    this.decoder = null
    if (!decoder || decoder.state === 'closed') {
      return
    }
    try {
      decoder.close()
    } catch {
      // Chrome closes the codec on error before this runs.
    }
  }

  private paint(frame: VideoFrame): void {
    if (this.destroyed) {
      frame.close()
      return
    }
    if (!this.context) {
      this.context = this.canvas.getContext('2d', { alpha: false, desynchronized: true })
        ?? this.canvas.getContext('2d')
    }
    if (!this.context) {
      frame.close()
      this.reportError(new Error('This browser cannot draw decoded video onto a canvas.'))
      return
    }
    if (this.canvas.width !== frame.displayWidth || this.canvas.height !== frame.displayHeight) {
      this.canvas.width = frame.displayWidth
      this.canvas.height = frame.displayHeight
    }
    this.context.drawImage(frame, 0, 0)
    const lagSeconds = Math.max(0, performance.now() / 1000 - frame.timestamp / 1e6)
    frame.close()
    if (!this.ready) {
      this.ready = true
      this.options.onReady?.()
    }
    this.emitStats(lagSeconds)
  }

  private emitStats(lagSeconds: number): void {
    this.options.onStats?.({
      codec: this.decoderInfo?.codec ?? '',
      width: this.decoderInfo?.width ?? 0,
      height: this.decoderInfo?.height ?? 0,
      lagSeconds,
    })
  }

  private reportError(error: unknown): void {
    if (this.destroyed) {
      return
    }
    this.options.onError?.(error instanceof Error ? error : new Error(String(error)))
  }
}

function decoderDescription(format: VideoFormat, keyframe: Uint8Array): Uint8Array {
  if (format === 'h264') {
    const record = extractAvcDecoderConfigurationRecord(keyframe)
    if (!record) {
      throw new Error('This H.264 stream is missing the parameter sets needed to decode it.')
    }
    return serializeAvcDecoderConfigurationRecord(record)
  }
  const record = extractHevcDecoderConfigurationRecord(keyframe)
  if (!record) {
    throw new Error('This H.265 stream is missing the parameter sets needed to decode it.')
  }
  return serializeHevcDecoderConfigurationRecord(record)
}
