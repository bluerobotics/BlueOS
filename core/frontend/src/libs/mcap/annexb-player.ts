/**
 * Live Annex-B video into a `<video>` element through the same MSE + fMP4 path as recorded playback.
 *
 * Tuned for a live inspector: each frame is flushed as its own fragment, duration is set once, and
 * the playhead is only snapped when it actually stalls. MSE is used instead of WebCodecs because
 * WebCodecs needs a secure context and BlueOS is served over HTTP.
 */
import { isKeyframe, ParameterSetCache, VideoFormat } from './codec'
import { appendSourceBuffer, isMediaSourceSupported, waitForSourceOpen } from './mse'
import {
  clampSampleDuration, Mp4MediaStream, probeDecoderInfo, VideoDecoderInfo,
} from './mux'

/** Drop queued camera frames rather than growing a backlog the inspector would then play through. */
const MAX_QUEUED_FRAMES = 8
/** Snap the playhead only when it has fallen this far behind; smaller values seek every few frames. */
const LIVE_LAG_SECONDS = 0.5
/** How much already-played media to keep. */
const KEEP_BEHIND_SECONDS = 2
/** Evict only when more than this extra media sits behind the keep-behind window. */
const EVICT_EXTRA_SECONDS = 1
/** Ask mediabunny for short fragments; live still force-flushes after each frame. */
const FRAGMENT_SECONDS = 0

export interface AnnexBMseStats {
  codec: string
  width: number
  height: number
  /** How far the playhead is behind the latest buffered frame. */
  lagSeconds: number
}

export interface AnnexBMsePlayerOptions {
  onReady?: () => void
  onError?: (error: Error) => void
  onStats?: (stats: AnnexBMseStats) => void
}

interface QueuedFrame {
  data: Uint8Array
  format: VideoFormat
  timestampSeconds: number
}

export class AnnexBMsePlayer {
  private mediaSource = new MediaSource()

  private objectUrl = URL.createObjectURL(this.mediaSource)

  private sourceBuffer: SourceBuffer | null = null

  private media: Mp4MediaStream | null = null

  private decoderInfo: VideoDecoderInfo | null = null

  private parameterSets = new ParameterSetCache()

  private controller = new AbortController()

  private opened: Promise<void>

  private operations: Promise<unknown> = Promise.resolve()

  private queue: QueuedFrame[] = []

  private pumping = false

  private destroyed = false

  private ready = false

  private originSeconds: number | null = null

  private lastTimestamp = 0

  private lastDuration = 1 / 30

  private pendingAppends: Uint8Array[] = []

  private appending = false

  constructor(
    private video: HTMLVideoElement,
    private options: AnnexBMsePlayerOptions = {},
  ) {
    if (!isMediaSourceSupported()) {
      throw new Error('This browser cannot play video, as it does not support Media Source Extensions.')
    }
    this.opened = waitForSourceOpen(this.mediaSource, this.controller.signal)
    this.video.addEventListener('timeupdate', this.onTimeUpdate)
    this.video.addEventListener('waiting', this.onWaiting)
    this.video.muted = true
    this.video.src = this.objectUrl
  }

  push(data: Uint8Array, format: VideoFormat, timestampSeconds?: number): void {
    if (this.destroyed || data.length === 0) {
      return
    }
    this.parameterSets.observeFrame(data, format)
    const stamped = timestampSeconds != null && Number.isFinite(timestampSeconds) && timestampSeconds > 0
      ? timestampSeconds
      : performance.now() / 1000
    this.queue.push({ data: data.slice(), format, timestampSeconds: stamped })
    if (this.queue.length > MAX_QUEUED_FRAMES) {
      this.dropToLatestKeyframe()
    }
    this.pump()
  }

  destroy(): void {
    this.destroyed = true
    this.queue = []
    this.pendingAppends = []
    this.controller.abort()
    this.media?.cancel().catch(() => undefined)
    this.media = null
    this.video.removeEventListener('timeupdate', this.onTimeUpdate)
    this.video.removeEventListener('waiting', this.onWaiting)
    this.video.pause()
    this.video.removeAttribute('src')
    this.video.load()
    URL.revokeObjectURL(this.objectUrl)
  }

  private dropToLatestKeyframe(): void {
    let keepFrom = 0
    for (let index = 0; index < this.queue.length; index += 1) {
      const frame = this.queue[index]
      if (isKeyframe(frame.data, frame.format)) {
        keepFrom = index
      }
    }
    if (keepFrom > 0) {
      this.queue.splice(0, keepFrom)
    } else if (this.queue.length > MAX_QUEUED_FRAMES) {
      this.queue.splice(0, this.queue.length - 1)
    }
  }

  private pump(): void {
    if (this.pumping) {
      return
    }
    this.pumping = true
    this.drain().catch((error) => this.reportError(error)).finally(() => {
      this.pumping = false
      if (this.queue.length > 0 && !this.destroyed) {
        this.pump()
      }
    })
  }

  private async drain(): Promise<void> {
    await this.opened
    while (this.queue.length > 0 && !this.destroyed) {
      const frame = this.queue.shift()
      if (frame) {
        // eslint-disable-next-line no-await-in-loop
        await this.handle(frame)
      }
    }
  }

  private async handle(frame: QueuedFrame): Promise<void> {
    const annexB = this.parameterSets.withParameterSets(frame.data, frame.format)
    if (annexB.length === 0) {
      return
    }
    const keyframe = isKeyframe(annexB, frame.format)
    if (!this.media) {
      if (!keyframe) {
        return
      }
      await this.configure(probeDecoderInfo(frame.format, annexB))
    }
    if (!this.media) {
      return
    }

    const timestamp = this.nextTimestamp(frame.timestampSeconds)
    await this.media.add({
      data: annexB,
      timestamp,
      duration: this.lastDuration,
      isKeyframe: keyframe,
    })
    await this.media.flushFragment()
    if (!this.ready) {
      this.ready = true
      this.options.onReady?.()
    }
    this.catchUp(false)
    this.emitStats()
  }

  private nextTimestamp(frameTimestamp: number): number {
    if (this.originSeconds === null) {
      this.originSeconds = frameTimestamp
      return 0
    }
    let timestamp = frameTimestamp - this.originSeconds
    if (timestamp <= this.lastTimestamp) {
      timestamp = this.lastTimestamp + this.lastDuration
    }
    this.lastDuration = clampSampleDuration(timestamp - this.lastTimestamp)
    this.lastTimestamp = timestamp
    return timestamp
  }

  private async configure(decoderInfo: VideoDecoderInfo): Promise<void> {
    this.decoderInfo = decoderInfo
    const mime = `video/mp4; codecs="${decoderInfo.codec}"`
    if (!MediaSource.isTypeSupported(mime)) {
      throw new Error(`This browser cannot play ${decoderInfo.format.toUpperCase()} video (${decoderInfo.codec}).`)
    }
    this.sourceBuffer = this.mediaSource.addSourceBuffer(mime)
    this.sourceBuffer.mode = 'segments'
    this.setLiveDuration()
    this.media = await Mp4MediaStream.open(
      decoderInfo,
      (data) => {
        this.enqueueAppend(data)
      },
      FRAGMENT_SECONDS,
    )
    this.emitStats()
  }

  /** Live streams do not have an end; setting duration while a buffer is updating throws. */
  private setLiveDuration(): void {
    if (this.mediaSource.readyState !== 'open' || this.sourceBuffer?.updating) {
      return
    }
    try {
      this.mediaSource.duration = Number.POSITIVE_INFINITY
    } catch {
      this.mediaSource.duration = 1e9
    }
  }

  private catchUp(force: boolean): void {
    const end = this.bufferedEnd()
    if (end <= 0) {
      return
    }
    const lag = end - this.video.currentTime
    if ((force || this.video.paused || lag > LIVE_LAG_SECONDS) && lag > 0.05) {
      this.video.currentTime = Math.max(0, end - 0.001)
      this.video.playbackRate = 1
    } else if (lag > 0.08) {
      this.video.playbackRate = 1.15
    } else {
      this.video.playbackRate = 1
    }
    if (this.video.paused) {
      this.video.play().catch(() => undefined)
    }
  }

  private bufferedEnd(): number {
    const { buffered } = this.video
    return buffered.length > 0 ? buffered.end(buffered.length - 1) : 0
  }

  private onTimeUpdate = (): void => {
    this.emitStats()
  }

  private onWaiting = (): void => {
    this.catchUp(true)
  }

  private emitStats(): void {
    if (this.destroyed) {
      return
    }
    this.options.onStats?.({
      codec: this.decoderInfo?.codec ?? '',
      width: this.decoderInfo?.width ?? 0,
      height: this.decoderInfo?.height ?? 0,
      lagSeconds: Math.max(0, this.bufferedEnd() - this.video.currentTime),
    })
  }

  private reportError(error: unknown): void {
    if (this.destroyed || error instanceof Error && error.name === 'AbortError') {
      return
    }
    this.options.onError?.(error instanceof Error ? error : new Error(String(error)))
  }

  private enqueueAppend(data: Uint8Array): void {
    this.pendingAppends.push(data)
    this.pumpAppend()
  }

  private pumpAppend(): void {
    if (this.appending) {
      return
    }
    this.appending = true
    this.drainAppend().catch((error) => this.reportError(error)).finally(() => {
      this.appending = false
      if (this.pendingAppends.length > 0 && !this.destroyed) {
        this.pumpAppend()
      }
    })
  }

  private async drainAppend(): Promise<void> {
    while (this.pendingAppends.length > 0 && !this.destroyed) {
      const data = this.pendingAppends.shift()
      if (!data) {
        continue
      }
      // eslint-disable-next-line no-await-in-loop
      await this.appendData(data)
    }
  }

  private async appendData(data: Uint8Array): Promise<void> {
    await this.run(async () => {
      try {
        await this.appendToBuffer(data)
      } catch (error) {
        if (!(error instanceof Error) || error.name !== 'QuotaExceededError') {
          throw error
        }
        await this.evict(true)
        await this.appendToBuffer(data)
      }
    })
    await this.run(() => this.evict(false))
  }

  private appendToBuffer(data: Uint8Array): Promise<void> {
    if (!this.sourceBuffer) {
      throw new Error('Source buffer is not ready.')
    }
    return appendSourceBuffer(
      this.sourceBuffer,
      data,
      this.controller.signal,
      'The browser rejected the video data.',
    )
  }

  private async evict(aggressive: boolean): Promise<void> {
    const buffer = this.sourceBuffer
    if (!buffer || buffer.buffered.length === 0) {
      return
    }
    const keepBehind = aggressive ? 0.25 : KEEP_BEHIND_SECONDS
    const extra = this.video.currentTime - keepBehind - buffer.buffered.start(0)
    if (extra > (aggressive ? 0 : EVICT_EXTRA_SECONDS)) {
      await this.removeRange(0, this.video.currentTime - keepBehind)
    }
  }

  private removeRange(start: number, end: number): Promise<void> {
    const buffer = this.sourceBuffer
    if (!buffer || buffer.updating) {
      return Promise.resolve()
    }
    return new Promise<void>((resolve) => {
      buffer.addEventListener('updateend', () => resolve(), { once: true })
      try {
        buffer.remove(start, end)
      } catch {
        resolve()
      }
    })
  }

  private run<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.operations.then(operation)
    this.operations = result.catch(() => undefined)
    return result
  }
}
