/**
 * Turns a raw video stream into frames a decoder can actually start on: skip leading junk, wait
 * for a keyframe, pull parameter sets if they only appeared at the start of the recording.
 */
import { isKeyframe, ParameterSetCache, VideoFormat } from './codec'
import VideoFrameStream, { scanParameterSets, UNDECODABLE_FRAMES_BEFORE_SKIP } from './frame-stream'
import { probeDecoderInfo, VideoDecoderInfo } from './mux'
import { McapIndexedReader } from './reader'
import { VideoTrack } from './video-track'

export interface DecodableFrame {
  logTime: bigint
  format: VideoFormat
  annexB: Uint8Array
  isKeyframe: boolean
}

export class DecodableFrameCursor {
  decoderInfo: VideoDecoderInfo | null = null

  keyframes = 0

  framesSkipped = 0

  framesCorrupt = 0

  private parameterSets = new ParameterSetCache()

  private needsKeyframe = true

  private skippedStreak = 0

  private scannedForParameterSets = false

  constructor(
    private stream: VideoFrameStream,
    private reader: McapIndexedReader,
    private track: VideoTrack,
    private skipEmptyPayloads = true,
  ) {}

  /** Next yielded frame must start a group of pictures, which is what a seek leaves the decoder needing. */
  requireKeyframe(): void {
    this.needsKeyframe = true
    this.skippedStreak = 0
  }

  async next(signal?: AbortSignal, maxReads = Infinity): Promise<DecodableFrame | null> {
    for (let reads = 0; reads < maxReads; reads += 1) {
      // eslint-disable-next-line no-await-in-loop
      const frame = await this.stream.next(signal)
      if (!frame) {
        return null
      }
      const annexB = this.parameterSets.withParameterSets(frame.data, frame.format)
      if (annexB.length === 0 && this.skipEmptyPayloads) {
        this.framesCorrupt += 1
        continue
      }
      const keyframe = annexB.length > 0 && isKeyframe(annexB, frame.format)
      if (this.needsKeyframe) {
        if (!keyframe) {
          this.framesSkipped += 1
          this.skippedStreak += 1
          if (this.skippedStreak >= UNDECODABLE_FRAMES_BEFORE_SKIP) {
            this.skippedStreak = 0
            // eslint-disable-next-line no-await-in-loop
            await this.stream.skipToKeyframeHint(signal)
          }
          continue
        }
        this.skippedStreak = 0
        if (!this.parameterSets.complete && !this.scannedForParameterSets) {
          this.scannedForParameterSets = true
          // eslint-disable-next-line no-await-in-loop
          await scanParameterSets(this.reader, this.track, this.parameterSets, signal)
        }
        const primed = this.parameterSets.withParameterSets(annexB, frame.format)
        if (!this.decoderInfo) {
          this.decoderInfo = probeDecoderInfo(frame.format, primed)
        }
        this.needsKeyframe = false
        this.keyframes += 1
        return {
          logTime: frame.logTime, format: frame.format, annexB: primed, isKeyframe: true,
        }
      }
      if (keyframe) {
        this.keyframes += 1
      }
      return {
        logTime: frame.logTime, format: frame.format, annexB, isKeyframe: keyframe,
      }
    }
    return null
  }
}
