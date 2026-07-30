/**
 * Streams video stored in an MCAP recording straight into a `<video>` element.
 *
 * Frames are read from the recording over range requests, wrapped into fragmented MP4 and handed to
 * Media Source Extensions, which decodes them with the browser's hardware decoder. MSE is used
 * instead of WebCodecs because WebCodecs is only available in secure contexts, and BlueOS is
 * normally served over plain HTTP.
 */
import {
  CodecConfig, ParameterSetCache, toMp4Sample, VideoFormat,
} from './codec'
import VideoFrameStream, { scanParameterSets, UNDECODABLE_FRAMES_BEFORE_SKIP } from './frame-stream'
import {
  buildFragment, buildInitSegment, MAXIMUM_SAMPLE_DURATION_US, MINIMUM_SAMPLE_DURATION_US, Mp4Sample,
} from './mp4'
import { McapIndexedReader } from './reader'
import { HttpByteSource } from './source'
import { listVideoTracks, VideoTrack } from './video-track'

const RESUME_TOLERANCE_SECONDS = 0.25

export interface McapVideoStats {
  bytesDownloaded: number
  bufferedAheadSeconds: number
  codec: string
  width: number
  height: number
  format: VideoFormat | null
  loading: boolean
}

export interface McapVideoPlayerOptions {
  /** How much media to keep ahead of the playhead. Smaller values save bandwidth on slow links. */
  bufferAheadSeconds?: number
  /** How much played back media to keep in memory before evicting it. */
  keepBehindSeconds?: number
  /** Media covered by a single MP4 fragment. */
  fragmentSeconds?: number
  onStats?: (stats: McapVideoStats) => void
  onError?: (error: Error) => void
}

interface PendingFrame {
  logTime: bigint
  format: VideoFormat
  data: Uint8Array
  isKeyframe: boolean
}

export interface McapVideoRecording {
  reader: McapIndexedReader
  tracks: VideoTrack[]
  durationSeconds: number
  startTime: bigint
}

export async function openMcapVideoRecording(url: string, signal?: AbortSignal): Promise<McapVideoRecording> {
  const reader = await McapIndexedReader.open(new HttpByteSource(url), { signal })
  const { startTime, endTime } = reader.summary
  return {
    reader,
    tracks: listVideoTracks(reader),
    durationSeconds: Number(endTime - startTime) / 1e9,
    startTime,
  }
}

export interface McapVideoSummary {
  durationSeconds: number
  tracks: VideoTrack[]
  /** Bytes transferred to read this summary, useful to explain the cost of browsing recordings. */
  bytesRead: number
}

/** Reads what a recording contains without downloading its chunk index. */
export async function readMcapVideoSummary(url: string, signal?: AbortSignal): Promise<McapVideoSummary> {
  const source = new HttpByteSource(url)
  const reader = await McapIndexedReader.open(source, { metadataOnly: true, signal })
  const { startTime, endTime } = reader.summary
  return {
    durationSeconds: Number(endTime - startTime) / 1e9,
    tracks: listVideoTracks(reader),
    bytesRead: source.bytesRead,
  }
}

export function isMediaSourceSupported(): boolean {
  return typeof window !== 'undefined' && 'MediaSource' in window
}

export class McapVideoPlayer {
  private mediaSource = new MediaSource()

  private objectUrl = URL.createObjectURL(this.mediaSource)

  private stream: VideoFrameStream

  private sourceBuffer: SourceBuffer | null = null

  private config: CodecConfig | null = null

  private parameterSets = new ParameterSetCache()

  private controller = new AbortController()

  private operations: Promise<unknown> = Promise.resolve()

  private fillTask: Promise<void> | null = null

  private pending: PendingFrame[] = []

  private needsKeyframe = true

  private skippedFrames = 0

  private lastSampleDuration = MINIMUM_SAMPLE_DURATION_US

  private sequence = 1

  private internalSeek = false

  /** Number of seeks currently pointing the stream at a new time. */
  private restarts = 0

  private reachedEnd = false

  private scannedForParameterSets = false

  private destroyed = false

  private loading = true

  private readonly bufferAheadSeconds: number

  private readonly keepBehindSeconds: number

  private readonly fragmentSeconds: number

  constructor(
    private video: HTMLVideoElement,
    private recording: McapVideoRecording,
    private track: VideoTrack,
    private options: McapVideoPlayerOptions = {},
  ) {
    this.stream = new VideoFrameStream(recording.reader, track)
    this.bufferAheadSeconds = options.bufferAheadSeconds ?? 8
    this.keepBehindSeconds = options.keepBehindSeconds ?? 30
    this.fragmentSeconds = options.fragmentSeconds ?? 0.5
  }

  async start(): Promise<void> {
    this.video.addEventListener('seeking', this.onSeeking)
    this.video.addEventListener('timeupdate', this.onTimeUpdate)
    this.video.addEventListener('waiting', this.onWaiting)

    const opened = new Promise<void>((resolve) => {
      this.mediaSource.addEventListener('sourceopen', () => resolve(), { once: true })
    })
    this.video.src = this.objectUrl
    await opened

    this.stream.seekToStart()
    this.scheduleFill()
  }

  destroy(): void {
    this.destroyed = true
    this.controller.abort()
    this.video.removeEventListener('seeking', this.onSeeking)
    this.video.removeEventListener('timeupdate', this.onTimeUpdate)
    this.video.removeEventListener('waiting', this.onWaiting)
    this.video.pause()
    this.video.removeAttribute('src')
    this.video.load()
    URL.revokeObjectURL(this.objectUrl)
  }

  get stats(): McapVideoStats {
    return {
      bytesDownloaded: this.stream.bytesRead,
      bufferedAheadSeconds: this.bufferedAhead(),
      codec: this.config?.codec ?? '',
      width: this.config?.width ?? 0,
      height: this.config?.height ?? 0,
      format: this.pending[0]?.format ?? null,
      loading: this.loading,
    }
  }

  private emitStats(): void {
    if (this.destroyed) {
      return
    }
    this.options.onStats?.(this.stats)
  }

  private bufferedAhead(): number {
    const { buffered, currentTime } = this.video
    for (let index = 0; index < buffered.length; index += 1) {
      if (currentTime >= buffered.start(index) - RESUME_TOLERANCE_SECONDS && currentTime <= buffered.end(index)) {
        return buffered.end(index) - currentTime
      }
    }
    // A playhead sitting in a gap still has media waiting after it. Ignoring that would leave the
    // filling loop convinced it has nothing buffered, and it would read on to the end of the file.
    for (let index = 0; index < buffered.length; index += 1) {
      if (buffered.start(index) > currentTime) {
        return buffered.end(index) - buffered.start(index)
      }
    }
    return 0
  }

  private onTimeUpdate = (): void => {
    this.scheduleFill()
  }

  private onWaiting = (): void => {
    this.alignPlayhead()
    this.scheduleFill()
  }

  private onSeeking = (): void => {
    if (this.internalSeek) {
      this.internalSeek = false
      return
    }
    if (this.bufferedAhead() > 0) {
      this.scheduleFill()
      return
    }
    this.restartAt(this.video.currentTime).catch((error) => this.reportError(error))
  }

  private reportError(error: unknown): void {
    if (this.destroyed || error instanceof Error && error.name === 'AbortError') {
      return
    }
    this.options.onError?.(error instanceof Error ? error : new Error(String(error)))
  }

  /** Restarts reading at a keyframe covering the requested time, dropping everything buffered. */
  private async restartAt(seconds: number): Promise<void> {
    this.restarts += 1
    try {
      await this.reopenAt(seconds)
    } finally {
      this.restarts -= 1
    }
    if (this.restarts === 0) {
      this.scheduleFill()
    }
  }

  private async reopenAt(seconds: number): Promise<void> {
    this.controller.abort()
    await this.fillTask?.catch(() => undefined)
    if (this.destroyed) {
      return
    }

    this.controller = new AbortController()
    this.pending = []
    this.needsKeyframe = true
    this.reachedEnd = false
    this.loading = true
    this.emitStats()

    if (this.sourceBuffer) {
      await this.run(() => this.removeRange(0, Infinity))
    }
    await this.stream.seekToKeyframe(seconds, this.controller.signal)
  }

  private scheduleFill(): void {
    // Filling while the stream is being pointed at a new time would read on from the old position,
    // which is both the wrong content and a needless download.
    if (this.destroyed || this.restarts > 0 || this.fillTask || this.reachedEnd) {
      return
    }
    if (this.sourceBuffer && this.bufferedAhead() >= this.bufferAheadSeconds) {
      return
    }
    this.fillTask = this.fill()
      .catch((error) => this.reportError(error))
      .finally(() => {
        this.fillTask = null
      })
  }

  private async fill(): Promise<void> {
    const { signal } = this.controller
    while (!this.destroyed && !signal.aborted && !this.reachedEnd) {
      if (this.sourceBuffer && this.bufferedAhead() >= this.bufferAheadSeconds) {
        return
      }

      // eslint-disable-next-line no-await-in-loop
      const frame = await this.stream.next(signal)
      if (!frame) {
        // eslint-disable-next-line no-await-in-loop
        await this.flushFragment(true)
        this.reachedEnd = true
        if (this.needsKeyframe) {
          throw new Error('This video stream holds no keyframe, so there is nothing that can be decoded.')
        }
        if (this.mediaSource.readyState === 'open') {
          this.mediaSource.endOfStream()
        }
        return
      }

      const sample = toMp4Sample(frame.data, frame.format, this.parameterSets)
      if (this.needsKeyframe) {
        if (!sample.isKeyframe) {
          this.skippedFrames += 1
          if (this.skippedFrames >= UNDECODABLE_FRAMES_BEFORE_SKIP) {
            this.skippedFrames = 0
            // eslint-disable-next-line no-await-in-loop
            await this.stream.skipToKeyframeHint(signal)
          }
          continue
        }
        this.skippedFrames = 0
        // eslint-disable-next-line no-await-in-loop
        await this.configure(frame.format)
        this.needsKeyframe = false
      }

      this.pending.push({ ...sample, logTime: frame.logTime, format: frame.format })
      if (this.pendingSeconds() >= this.fragmentSeconds) {
        // eslint-disable-next-line no-await-in-loop
        await this.flushFragment()
      }
    }
  }

  private pendingSeconds(): number {
    if (this.pending.length < 2) {
      return 0
    }
    const first = this.pending[0].logTime
    const last = this.pending[this.pending.length - 1].logTime
    return Number(last - first) / 1e9
  }

  /** Creates or updates the source buffer from the parameter sets seen so far. */
  private async configure(format: VideoFormat): Promise<void> {
    if (!this.parameterSets.complete && !this.scannedForParameterSets) {
      this.scannedForParameterSets = true
      await scanParameterSets(this.recording.reader, this.track, this.parameterSets, this.controller.signal)
    }
    const config = this.parameterSets.buildConfig(format)
    if (!config) {
      throw new Error(`This ${format.toUpperCase()} stream was recorded without the parameter sets`
        + ' needed to decode it, so no player can show it.')
    }

    const mime = `video/mp4; codecs="${config.codec}"`
    if (!this.sourceBuffer) {
      if (!MediaSource.isTypeSupported(mime)) {
        throw new Error(`This browser cannot play ${format.toUpperCase()} video (${config.codec}).`)
      }
      this.sourceBuffer = this.mediaSource.addSourceBuffer(mime)
      this.sourceBuffer.mode = 'segments'
      this.mediaSource.duration = this.stream.durationSeconds
    } else if (config.codec !== this.config?.codec) {
      const buffer = this.sourceBuffer
      await this.run(async () => buffer.changeType(mime))
    } else if (config.width === this.config?.width && config.height === this.config?.height) {
      return
    }

    this.config = config
    await this.appendData(buildInitSegment(config))
    this.emitStats()
  }

  private async flushFragment(flushAll = false): Promise<void> {
    const { signal } = this.controller
    // The last frame is held back because its duration is only known once the next one arrives.
    const frames = flushAll ? this.pending : this.pending.slice(0, -1)
    if (frames.length === 0) {
      return
    }
    this.pending = flushAll ? [] : this.pending.slice(-1)

    const samples: Mp4Sample[] = frames.map((frame, index) => {
      const next = frames[index + 1] ?? this.pending[0]
      if (next) {
        const delta = Math.round(Number(next.logTime - frame.logTime) / 1000)
        this.lastSampleDuration = Math.min(Math.max(delta, MINIMUM_SAMPLE_DURATION_US), MAXIMUM_SAMPLE_DURATION_US)
      }
      return { data: frame.data, duration: this.lastSampleDuration, isKeyframe: frame.isKeyframe }
    })

    const startSeconds = this.stream.toSeconds(frames[0].logTime)
    const baseMediaDecodeTime = Math.round(startSeconds * 1e6)
    await this.appendData(buildFragment(samples, baseMediaDecodeTime, this.sequence))
    this.sequence += 1

    // A seek that happened while this fragment was being appended has already moved the playhead
    // where it belongs, and reading has restarted elsewhere.
    if (!signal.aborted) {
      this.alignPlayhead()
    }
    this.loading = false
    this.emitStats()
  }

  /**
   * Moves the playhead onto media that exists. Recordings start on a keyframe that is a little later
   * than asked for, and they can hold gaps where a stream dropped out; since reading only goes
   * forward, waiting for the missing media would stall playback for good.
   */
  private alignPlayhead(): void {
    const { buffered, currentTime } = this.video
    for (let index = 0; index < buffered.length; index += 1) {
      if (currentTime >= buffered.start(index) - RESUME_TOLERANCE_SECONDS && currentTime <= buffered.end(index)) {
        return
      }
    }
    for (let index = 0; index < buffered.length; index += 1) {
      const start = buffered.start(index)
      if (start > currentTime) {
        this.internalSeek = true
        this.video.currentTime = start + 0.001
        return
      }
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
    const buffer: SourceBuffer = this.sourceBuffer
    return new Promise<void>((resolve, reject) => {
      function cleanup(): void {
        buffer.removeEventListener('updateend', onDone)
        buffer.removeEventListener('error', onFail)
      }
      function onDone(): void {
        cleanup()
        resolve()
      }
      function onFail(): void {
        cleanup()
        reject(new Error('The browser rejected the video data.'))
      }
      buffer.addEventListener('updateend', onDone)
      buffer.addEventListener('error', onFail)
      try {
        buffer.appendBuffer(data)
      } catch (error) {
        cleanup()
        reject(error)
      }
    })
  }

  private async evict(aggressive: boolean): Promise<void> {
    const buffer = this.sourceBuffer
    if (!buffer || buffer.buffered.length === 0) {
      return
    }
    const keepBehind = aggressive ? 1 : this.keepBehindSeconds
    const limit = this.video.currentTime - keepBehind
    if (buffer.buffered.start(0) < limit) {
      await this.removeRange(0, limit)
    }
  }

  private removeRange(start: number, end: number): Promise<void> {
    const buffer = this.sourceBuffer
    if (!buffer) {
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

  /** Serializes source buffer operations, which may only run one at a time. */
  private run<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.operations.then(operation)
    this.operations = result.catch(() => undefined)
    return result
  }
}
