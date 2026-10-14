/**
 * Streams video stored in an MCAP recording straight into a `<video>` element.
 *
 * Frames are read from the recording over range requests, wrapped into fragmented MP4 and handed to
 * Media Source Extensions, which decodes them with the browser's hardware decoder. MSE is used
 * instead of WebCodecs because WebCodecs is only available in secure contexts, and BlueOS is
 * normally served over plain HTTP.
 */
import { sleep } from './abort'
import { listMcapChannels, McapRecordingChannel } from './channels'
import { VideoFormat } from './codec'
import VideoFrameStream from './frame-stream'
import { DecodableFrameCursor } from './frames'
import { appendSourceBuffer, isMediaSourceSupported, waitForSourceOpen } from './mse'
import {
  AnnexBFrame, clampSampleDuration, Mp4MediaStream, VideoDecoderInfo,
} from './mux'
import { McapIndexedReader, PrefixScanProgress } from './reader'
import { HttpByteSource } from './source'
import { listVideoTracks, VideoTrack } from './video-track'

const RESUME_TOLERANCE_SECONDS = 0.25

/** How short of the recorded span the buffered media may end and still count as the whole of it. */
const COMPLETE_TOLERANCE_SECONDS = 2
/** How often an ongoing recording is checked for chunks written after the player opened. */
const FOLLOW_POLL_MS = 750

export interface McapVideoStats {
  bytesDownloaded: number
  bufferedAheadSeconds: number
  codec: string
  width: number
  height: number
  format: VideoFormat | null
  loading: boolean
  /** True while an ongoing recording has no further frames yet and the player is polling for them. */
  waiting: boolean
  /** Frames read out of the recording, and how many of them started a group of pictures. */
  framesRead: number
  keyframes: number
  /** Frames the recorder never wrote, seen as gaps in its sequence numbers. */
  framesLost: number
  /** Frames read but not handed to the decoder, which is what happens before the first keyframe. */
  framesSkipped: number
  /** Frames holding no readable video data, so either truncated or corrupted in the recording. */
  framesCorrupt: number
  /** Frames the browser decoder handled and let go of, as it counts them itself. */
  framesDecoded: number
  framesDropped: number
  /** Times the browser refused the video data or failed to decode it. */
  decodeErrors: number
  /** Frame rate and bitrate of the frames being read, measured from their recorded timestamps. */
  frameRate: number
  bitrate: number
}

export interface McapVideoPlayerOptions {
  /** How much media to keep ahead of the playhead. Smaller values save bandwidth on slow links. */
  bufferAheadSeconds?: number
  /** How much played back media to keep in memory before evicting it. */
  keepBehindSeconds?: number
  /** Media covered by a single MP4 fragment. */
  fragmentSeconds?: number
  /** Open at the last keyframe, so an ongoing recording shows the latest frames first. */
  startAtEnd?: boolean
  /** Open at this time in the recording, taking priority over `startAtEnd`. */
  startSeconds?: number
  /** Keep reading after the written prefix, so an ongoing recording can play through new chunks. */
  follow?: boolean
  onStats?: (stats: McapVideoStats) => void
  onError?: (error: Error) => void
  onExtended?: () => void
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
  channels: McapRecordingChannel[]
  durationSeconds: number
  startTime: bigint
}

export interface McapVideoOpenOptions {
  indexUrl?: string
  signal?: AbortSignal
  onProgress?: (progress: PrefixScanProgress) => void
}

export async function openMcapVideoRecording(
  url: string,
  options: McapVideoOpenOptions = {},
): Promise<McapVideoRecording> {
  const { indexUrl, signal, onProgress } = options
  const reader = await McapIndexedReader.open(new HttpByteSource(url), { indexUrl, signal, onProgress })
  const { startTime, endTime } = reader.summary
  return {
    reader,
    tracks: listVideoTracks(reader),
    channels: listMcapChannels(reader),
    durationSeconds: Number(endTime - startTime) / 1e9,
    startTime,
  }
}

export interface McapVideoSummary {
  durationSeconds: number
  started: number
  ended: number
  tracks: VideoTrack[]
  channels: McapRecordingChannel[]
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
    started: Number(startTime) / 1e9,
    ended: Number(endTime) / 1e9,
    tracks: listVideoTracks(reader),
    channels: listMcapChannels(reader),
    bytesRead: source.bytesRead,
  }
}

export { isMediaSourceSupported } from './mse'

export class McapVideoPlayer {
  private mediaSource = new MediaSource()

  private objectUrl = URL.createObjectURL(this.mediaSource)

  private stream: VideoFrameStream

  private cursor: DecodableFrameCursor

  private sourceBuffer: SourceBuffer | null = null

  private decoderInfo: VideoDecoderInfo | null = null

  private media: Mp4MediaStream | null = null

  private controller = new AbortController()

  private operations: Promise<unknown> = Promise.resolve()

  private fillTask: Promise<void> | null = null

  private pending: PendingFrame[] = []

  private needsKeyframe = true

  private decodeErrors = 0

  private lastSampleDuration = 0.033

  /** Time the player moved the playhead to itself, which needs no restart of its own. */
  private internalSeekTarget: number | null = null

  /** Time a queued restart has to land on, or null when nothing is waiting to be seeked to. */
  private queuedRestartSeconds: number | null = null

  /** Whether a seek is currently pointing the stream at a new time. */
  private restarting = false

  private reachedEnd = false

  private destroyed = false

  private loading = true

  private waiting = false

  /**
   * True until the first fragment is in the buffer. Seeking events before that would restart
   * reading at time 0 and drop the keyframe `start()` just found.
   */
  private priming = true

  /**
   * False after the viewer pauses, so catching up to the latest frames does not start playback on
   * its own.
   */
  wantPlaying = true

  private readonly follow: boolean

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
    this.cursor = new DecodableFrameCursor(this.stream, recording.reader, track)
    this.bufferAheadSeconds = options.bufferAheadSeconds ?? 8
    this.keepBehindSeconds = options.keepBehindSeconds ?? 30
    this.fragmentSeconds = options.fragmentSeconds ?? 0.5
    this.follow = options.follow ?? false
  }

  setWantPlaying(playing: boolean): void {
    this.wantPlaying = playing
  }

  async start(): Promise<void> {
    this.video.addEventListener('seeking', this.onSeeking)
    this.video.addEventListener('timeupdate', this.onTimeUpdate)
    this.video.addEventListener('waiting', this.onWaiting)
    this.video.addEventListener('error', this.onMediaError)

    const opened = waitForSourceOpen(this.mediaSource)
    this.video.src = this.objectUrl
    await opened

    if (this.options.startSeconds != null) {
      await this.stream.seekToKeyframe(this.options.startSeconds, this.controller.signal)
    } else if (this.options.startAtEnd) {
      await this.stream.seekToKeyframe(this.stream.durationSeconds, this.controller.signal)
    } else {
      this.stream.seekToStart()
    }
    this.scheduleFill()
  }

  /** Drops media held for a different time and starts reading from a keyframe covering `seconds`. */
  seek(seconds: number): void {
    const duration = this.stream.durationSeconds
    const target = Math.max(0, Math.min(seconds, duration))
    this.restartAt(target).catch((error) => this.reportError(error))
  }

  destroy(): void {
    this.destroyed = true
    this.controller.abort()
    this.media?.cancel().catch(() => undefined)
    this.media = null
    this.video.removeEventListener('seeking', this.onSeeking)
    this.video.removeEventListener('timeupdate', this.onTimeUpdate)
    this.video.removeEventListener('waiting', this.onWaiting)
    this.video.removeEventListener('error', this.onMediaError)
    this.video.pause()
    this.video.removeAttribute('src')
    this.video.load()
    URL.revokeObjectURL(this.objectUrl)
  }

  get stats(): McapVideoStats {
    const {
      framesRead, framesLost, frameRate, bitrate,
    } = this.stream.stats
    const quality = this.video.getVideoPlaybackQuality?.()
    return {
      bytesDownloaded: this.stream.bytesRead,
      bufferedAheadSeconds: this.bufferedAhead(),
      codec: this.decoderInfo?.codec ?? '',
      width: this.decoderInfo?.width ?? 0,
      height: this.decoderInfo?.height ?? 0,
      format: this.pending[0]?.format ?? null,
      loading: this.loading,
      waiting: this.waiting,
      framesRead,
      keyframes: this.cursor.keyframes,
      framesLost,
      framesSkipped: this.cursor.framesSkipped,
      framesCorrupt: this.cursor.framesCorrupt,
      framesDecoded: quality?.totalVideoFrames ?? 0,
      framesDropped: quality?.droppedVideoFrames ?? 0,
      decodeErrors: this.decodeErrors,
      frameRate,
      bitrate,
    }
  }

  private emitStats(): void {
    if (this.destroyed) {
      return
    }
    this.options.onStats?.(this.stats)
  }

  /** Media covering the playhead itself, which is the only media it can play from where it is. */
  private bufferedFromPlayhead(): number {
    const { buffered, currentTime } = this.video
    for (let index = 0; index < buffered.length; index += 1) {
      if (currentTime >= buffered.start(index) - RESUME_TOLERANCE_SECONDS && currentTime <= buffered.end(index)) {
        return buffered.end(index) - currentTime
      }
    }
    return 0
  }

  private bufferedAhead(): number {
    const covering = this.bufferedFromPlayhead()
    if (covering > 0) {
      return covering
    }
    // A playhead sitting in a gap still has media waiting after it. Ignoring that would leave the
    // filling loop convinced it has nothing buffered, and it would read on to the end of the file.
    const { buffered, currentTime } = this.video
    for (let index = 0; index < buffered.length; index += 1) {
      if (buffered.start(index) > currentTime) {
        return buffered.end(index) - buffered.start(index)
      }
    }
    return 0
  }

  private bufferedEnd(): number {
    const { buffered } = this.video
    return buffered.length > 0 ? buffered.end(buffered.length - 1) : 0
  }

  /**
   * Tells the decoder there is nothing left to play, but only once the media held covers the
   * recording from its start to its end. Ending the stream makes the timeline seekable only where
   * media is already buffered, so following new chunks — or a long recording that has evicted its
   * start — would trap the playhead there and refuse scrubbing into the past.
   */
  private signalEndOfStream(): void {
    if (this.mediaSource.readyState !== 'open') {
      return
    }
    const { buffered } = this.video
    if (buffered.length === 0 || buffered.start(0) > COMPLETE_TOLERANCE_SECONDS) {
      return
    }
    if (this.bufferedEnd() < this.stream.durationSeconds - COMPLETE_TOLERANCE_SECONDS) {
      return
    }
    this.mediaSource.endOfStream()
  }

  private onTimeUpdate = (): void => {
    this.scheduleFill()
    this.emitStats()
  }

  private onMediaError = (): void => {
    if (this.video.error?.code === MediaError.MEDIA_ERR_DECODE) {
      this.decodeErrors += 1
      this.emitStats()
    }
  }

  private onWaiting = (): void => {
    this.alignPlayhead()
    this.scheduleFill()
  }

  private onSeeking = (): void => {
    // Compared against the playhead rather than trusted on its own: a seek of the viewer's that
    // landed elsewhere has to restart reading, however it interleaved with the player's own.
    const internalTarget = this.internalSeekTarget
    this.internalSeekTarget = null
    if (this.priming || this.video.buffered.length === 0) {
      return
    }
    if (internalTarget !== null && Math.abs(this.video.currentTime - internalTarget) < RESUME_TOLERANCE_SECONDS) {
      return
    }
    if (this.bufferedFromPlayhead() > 0) {
      // In-buffer scrubbing can play from what is already held. A restart already aiming somewhere
      // else is the viewer leaving that media; the browser snapping back onto it must not win.
      if (this.restarting || this.queuedRestartSeconds !== null) {
        return
      }
      this.scheduleFill()
      return
    }
    this.restartAt(this.video.currentTime).catch((error) => this.reportError(error))
  }

  private reportError(error: unknown): void {
    if (this.destroyed || error instanceof Error && error.name === 'AbortError') {
      return
    }
    // Reading stops here, so this is the last chance to report what it cost and got through.
    this.emitStats()
    this.options.onError?.(error instanceof Error ? error : new Error(String(error)))
  }

  /**
   * Restarts reading at a keyframe covering the requested time, dropping everything buffered.
   *
   * Restarts run one at a time: a second seek starting while one is under way would abort the reads
   * the first had just begun, leaving nothing buffered and no filling scheduled to recover from it.
   * Seeks arriving meanwhile replace the queued time instead, so only the last one is honoured.
   */
  private async restartAt(seconds: number): Promise<void> {
    this.queuedRestartSeconds = seconds
    this.reachedEnd = false
    if (this.restarting) {
      return
    }

    this.restarting = true
    try {
      while (this.queuedRestartSeconds !== null && !this.destroyed) {
        const target = this.queuedRestartSeconds
        this.queuedRestartSeconds = null
        // eslint-disable-next-line no-await-in-loop
        await this.reopenAt(target)
      }
    } finally {
      this.restarting = false
    }
    this.scheduleFill()
  }

  private async reopenAt(seconds: number): Promise<void> {
    this.controller.abort()
    await this.fillTask?.catch(() => undefined)
    await this.media?.cancel().catch(() => undefined)
    this.media = null
    if (this.destroyed) {
      return
    }

    this.controller = new AbortController()
    this.pending = []
    this.cursor.requireKeyframe()
    this.needsKeyframe = true
    this.reachedEnd = false
    this.loading = true
    this.waiting = false
    this.priming = true
    this.emitStats()

    if (this.sourceBuffer) {
      await this.run(() => this.removeRange(0, Infinity))
      this.restoreDuration()
    }
    await this.stream.seekToKeyframe(seconds, this.controller.signal)
    this.internalSeekTarget = seconds
    this.video.currentTime = seconds
  }

  /** Puts the recorded span back on the media, which ending the stream may have cut short. */
  private restoreDuration(): void {
    const { durationSeconds } = this.stream
    if (this.mediaSource.readyState !== 'open' || this.mediaSource.duration >= durationSeconds) {
      return
    }
    this.mediaSource.duration = durationSeconds
  }

  private scheduleFill(): void {
    // Filling while the stream is being pointed at a new time would read on from the old position,
    // which is both the wrong content and a needless download.
    if (this.destroyed || this.restarting || this.fillTask || this.reachedEnd) {
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
      const frame = await this.cursor.next(signal)
      if (!frame) {
        // eslint-disable-next-line no-await-in-loop
        await this.flushFragment(true, !this.follow)
        if (this.follow) {
          this.loading = false
          this.waiting = true
          this.emitStats()
          // eslint-disable-next-line no-await-in-loop
          const grew = await this.waitForNewData(signal)
          this.waiting = false
          this.emitStats()
          if (grew) {
            this.restoreDuration()
            this.options.onExtended?.()
            continue
          }
          return
        }
        this.reachedEnd = true
        if (this.needsKeyframe) {
          throw new Error('This video stream holds no keyframe, so there is nothing that can be decoded.')
        }
        this.signalEndOfStream()
        return
      }

      if (!this.media) {
        const info = this.cursor.decoderInfo
        if (!info) {
          continue
        }
        // eslint-disable-next-line no-await-in-loop
        await this.configure(info)
        this.needsKeyframe = false
      }

      this.pending.push({
        logTime: frame.logTime, format: frame.format, data: frame.annexB, isKeyframe: frame.isKeyframe,
      })
      if (this.pendingSeconds() >= this.fragmentSeconds) {
        // eslint-disable-next-line no-await-in-loop
        await this.flushFragment()
      }
    }
  }

  private async waitForNewData(signal: AbortSignal): Promise<boolean> {
    while (!this.destroyed && !signal.aborted) {
      // eslint-disable-next-line no-await-in-loop
      if (await this.recording.reader.extendWrittenPrefix(signal)) {
        return true
      }
      try {
        // eslint-disable-next-line no-await-in-loop
        await sleep(FOLLOW_POLL_MS, signal)
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          return false
        }
        throw error
      }
    }
    return false
  }

  private pendingSeconds(): number {
    if (this.pending.length < 2) {
      return 0
    }
    const first = this.pending[0].logTime
    const last = this.pending[this.pending.length - 1].logTime
    return Number(last - first) / 1e9
  }

  /** Creates or updates the source buffer from the decoder info of the first playable keyframe. */
  private async configure(info: VideoDecoderInfo): Promise<void> {
    this.decoderInfo = info

    const mime = `video/mp4; codecs="${info.codec}"`
    if (!this.sourceBuffer) {
      if (!MediaSource.isTypeSupported(mime)) {
        throw new Error(`This browser cannot play ${info.format.toUpperCase()} video (${info.codec}).`)
      }
      this.sourceBuffer = this.mediaSource.addSourceBuffer(mime)
      this.sourceBuffer.mode = 'segments'
      this.mediaSource.duration = this.stream.durationSeconds
    }

    if (!this.media) {
      this.media = await Mp4MediaStream.open(
        info,
        (data) => this.appendData(data),
        this.fragmentSeconds,
      )
    }
    this.emitStats()
  }

  private async flushFragment(flushAll = false, finalize = flushAll): Promise<void> {
    const { signal } = this.controller
    const frames = flushAll ? this.pending : this.pending.slice(0, -1)
    if (frames.length === 0 || !this.media) {
      return
    }
    this.pending = flushAll ? [] : this.pending.slice(-1)

    for (let index = 0; index < frames.length; index += 1) {
      const frame = frames[index]
      const next = frames[index + 1] ?? this.pending[0]
      if (next) {
        this.lastSampleDuration = clampSampleDuration(Number(next.logTime - frame.logTime) / 1e9)
      }
      const packet: AnnexBFrame = {
        data: frame.data,
        timestamp: this.stream.toSeconds(frame.logTime),
        duration: this.lastSampleDuration,
        isKeyframe: frame.isKeyframe,
      }
      // eslint-disable-next-line no-await-in-loop
      await this.media.add(packet)
    }

    if (finalize) {
      await this.media.finalize()
      this.media = null
    }

    if (!signal.aborted) {
      this.alignPlayhead()
      if (this.wantPlaying && this.video.paused) {
        this.video.play().catch(() => undefined)
      }
    }
    this.priming = false
    this.loading = false
    this.emitStats()
  }

  /**
   * Moves the playhead onto media that exists. Recordings start on a keyframe that is a little later
   * than asked for, and they can hold gaps where a stream dropped out; since reading only goes
   * forward, waiting for the missing media would stall playback for good.
   */
  private alignPlayhead(): void {
    // A restart on its way drops everything buffered and reads the media the playhead is waiting for,
    // so moving it now would only take it off the time that was asked for.
    if (this.restarting || this.queuedRestartSeconds !== null) {
      return
    }
    const { buffered, currentTime } = this.video
    if (buffered.length === 0) {
      return
    }
    for (let index = 0; index < buffered.length; index += 1) {
      if (currentTime >= buffered.start(index) - RESUME_TOLERANCE_SECONDS && currentTime <= buffered.end(index)) {
        return
      }
    }
    // Snap onto the nearest range. A seek to the end of an ongoing file lands after the last keyframe,
    // and a recording that only holds video in part of its span has nothing at the time that was
    // asked for; waiting there would freeze on an empty playhead.
    let nearestStart = buffered.start(0)
    let nearestDistance = Number.POSITIVE_INFINITY
    for (let index = 0; index < buffered.length; index += 1) {
      const start = buffered.start(index)
      const end = buffered.end(index)
      const distance = currentTime < start ? start - currentTime : currentTime > end ? currentTime - end : 0
      if (distance < nearestDistance) {
        nearestDistance = distance
        nearestStart = start
      }
    }
    this.internalSeekTarget = nearestStart + 0.001
    this.video.currentTime = this.internalSeekTarget
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
      undefined,
      'The browser rejected the video data.',
    )
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
