/**
 * Writes a video stream of an MCAP recording, or a part of one, out as an MP4 file in the browser.
 *
 * The frames stored in the recording are already H264 or H265, so saving is a matter of wrapping them
 * in a container: nothing is decoded or encoded, and the picture is exactly what was recorded. The
 * file is not fragmented, so players and editors that only understand ordinary MP4 read it too.
 *
 * Saving a range is what keeps the transfer down. Frames live inside compressed MCAP chunks that also
 * carry every other topic recorded at the same time, so a chunk can only be read whole: saving a
 * whole stream means downloading practically the whole recording, while saving a minute of it only
 * downloads the chunks that minute falls in.
 */
import { CodecConfig, ParameterSetCache, toMp4Sample } from './codec'
import VideoFrameStream, { scanParameterSets, UNDECODABLE_FRAMES_BEFORE_SKIP } from './frame-stream'
import {
  buildFileHeader, buildMdat, buildMoov, MAXIMUM_SAMPLE_DURATION_US, MDAT_HEADER_SIZE,
  MINIMUM_SAMPLE_DURATION_US, Mp4SampleTable,
} from './mp4'
import { McapVideoRecording } from './player'
import { VideoTrack } from './video-track'

/** Media held by each `mdat` box, which is also how samples are grouped for the sample tables. */
const CHUNK_SECONDS = 1
/**
 * Media collected before it is handed over as a blob. Blobs live in the browser's own storage, which
 * spills to disk, so recordings far larger than memory can still be saved.
 */
const BLOB_PART_BYTES = 32 * 1024 * 1024

export interface Mp4ExportProgress {
  /** Media written so far. */
  seconds: number
  durationSeconds: number
  bytes: number
}

/** Part of a recording to save, in seconds from its start, as the player counts them. */
export interface Mp4ExportRange {
  startSeconds: number
  /** Infinity to save through to the end of the recording. */
  endSeconds: number
}

export interface Mp4ExportOptions {
  /** Defaults to the whole stream. */
  range?: Mp4ExportRange
  onProgress?: (progress: Mp4ExportProgress) => void
  signal?: AbortSignal
}

function abortError(): Error {
  const error = new Error('The export was cancelled.')
  error.name = 'AbortError'
  return error
}

/** How long a sample lasts, as the gap to the frame that follows it, within what MP4 can express. */
function sampleDuration(logTime: bigint, nextLogTime: bigint): number {
  const delta = Math.round(Number(nextLogTime - logTime) / 1000)
  return Math.min(Math.max(delta, MINIMUM_SAMPLE_DURATION_US), MAXIMUM_SAMPLE_DURATION_US)
}

interface HeldSample {
  data: Uint8Array
  logTime: bigint
  isKeyframe: boolean
}

class Mp4FileBuilder {
  private table: Mp4SampleTable = {
    durations: [], sizes: [], syncSamples: [], chunks: [],
  }

  private blobs: Blob[] = []

  private parts: Uint8Array[] = []

  private partBytes = 0

  private payloads: Uint8Array[] = []

  private chunkStart: bigint | null = null

  bytes = 0

  constructor(private config: CodecConfig) {
    this.write(buildFileHeader())
  }

  get samples(): number {
    return this.table.sizes.length
  }

  add(sample: HeldSample, duration: number): void {
    this.table.durations.push(duration)
    this.table.sizes.push(sample.data.length)
    if (sample.isKeyframe) {
      this.table.syncSamples.push(this.table.sizes.length)
    }
    this.payloads.push(sample.data)
    this.chunkStart ??= sample.logTime
    if (Number(sample.logTime - this.chunkStart) / 1e9 >= CHUNK_SECONDS) {
      this.flushChunk()
    }
  }

  finish(): Blob {
    this.flushChunk()
    this.write(buildMoov(this.config, this.table))
    this.blobs.push(new Blob(this.parts))
    this.parts = []
    return new Blob(this.blobs, { type: 'video/mp4' })
  }

  private flushChunk(): void {
    if (this.payloads.length === 0) {
      return
    }
    this.table.chunks.push({ offset: this.bytes + MDAT_HEADER_SIZE, samples: this.payloads.length })
    this.write(buildMdat(this.payloads))
    this.payloads = []
    this.chunkStart = null
  }

  private write(data: Uint8Array): void {
    this.parts.push(data)
    this.bytes += data.length
    this.partBytes += data.length
    if (this.partBytes >= BLOB_PART_BYTES) {
      this.blobs.push(new Blob(this.parts))
      this.parts = []
      this.partBytes = 0
    }
  }
}

/** Reads a video stream, or the requested range of it, and returns it as an MP4 file ready to save. */
export async function exportTrackAsMp4(
  recording: McapVideoRecording,
  track: VideoTrack,
  options: Mp4ExportOptions = {},
): Promise<Blob> {
  const { onProgress, signal, range } = options
  const stream = new VideoFrameStream(recording.reader, track)
  const startSeconds = Math.max(0, range?.startSeconds ?? 0)
  const endSeconds = Math.min(range?.endSeconds ?? Infinity, stream.durationSeconds)
  // Video can only be decoded from a keyframe on, so a range starts at the one covering its start.
  // That is also why the file may open a moment earlier than asked for.
  if (startSeconds > 0) {
    await stream.seekToKeyframe(startSeconds, signal)
  } else {
    stream.seekToStart()
  }
  const endLogTime = range && Number.isFinite(range.endSeconds) ? stream.toLogTime(range.endSeconds) : null

  const parameterSets = new ParameterSetCache()
  let builder: Mp4FileBuilder | null = null
  let held: HeldSample | null = null
  let duration = MINIMUM_SAMPLE_DURATION_US
  let undecodable = 0

  for (;;) {
    if (signal?.aborted) {
      throw abortError()
    }
    // eslint-disable-next-line no-await-in-loop
    const frame = await stream.next(signal)
    if (!frame) {
      break
    }
    // The first frame past the end is not saved, but it does say how long the one before it lasts.
    if (endLogTime !== null && frame.logTime > endLogTime) {
      if (builder && held) {
        builder.add(held, sampleDuration(held.logTime, frame.logTime))
        held = null
      }
      break
    }

    const sample = toMp4Sample(frame.data, frame.format, parameterSets)
    if (!builder) {
      if (!sample.isKeyframe) {
        undecodable += 1
        if (undecodable >= UNDECODABLE_FRAMES_BEFORE_SKIP) {
          undecodable = 0
          // eslint-disable-next-line no-await-in-loop
          await stream.skipToKeyframeHint(signal)
        }
        continue
      }
      if (!parameterSets.complete) {
        // eslint-disable-next-line no-await-in-loop
        await scanParameterSets(recording.reader, track, parameterSets, signal)
      }
      const config = parameterSets.buildConfig(frame.format)
      if (!config) {
        throw new Error(`This ${frame.format.toUpperCase()} stream was recorded without the parameter sets`
          + ' needed to decode it, so it cannot be saved as a video file.')
      }
      builder = new Mp4FileBuilder(config)
    }

    if (held) {
      duration = sampleDuration(held.logTime, frame.logTime)
      builder.add(held, duration)
      onProgress?.({
        seconds: Math.max(0, stream.toSeconds(held.logTime) - startSeconds),
        durationSeconds: Math.max(endSeconds - startSeconds, 0),
        bytes: builder.bytes,
      })
    }
    held = { data: sample.data, logTime: frame.logTime, isKeyframe: sample.isKeyframe }
  }

  if (!builder) {
    throw new Error(range
      ? 'The selected part of this video stream holds no keyframe, so there is nothing that can be saved.'
      : 'This video stream holds no keyframe, so there is nothing that can be saved.')
  }
  if (held) {
    // The last frame keeps the duration of the one before it, since nothing follows to measure it.
    builder.add(held, duration)
  }
  return builder.finish()
}

/**
 * Hands a file to the browser to save. A download link works in every browser and needs no secure
 * context, unlike the file system access API, but it has to be in the document to be clicked, and
 * releasing the file before the browser has taken it would cancel the download.
 */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  setTimeout(() => {
    link.remove()
    URL.revokeObjectURL(url)
  }, 0)
}
