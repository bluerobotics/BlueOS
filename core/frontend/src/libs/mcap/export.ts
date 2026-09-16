/**
 * Writes a video stream of an MCAP recording, or a part of one, out as an MP4 file in the browser.
 *
 * The frames stored in the recording are already H264 or H265, so saving is a matter of wrapping them
 * in a container: nothing is decoded or encoded, and the picture is exactly what was recorded. The
 * file is not fragmented, so players and editors that only understand ordinary MP4 read it too.
 *
 * Saving a range is what keeps the transfer down. Frames live inside compressed MCAP chunks that also
 * carry every other topic recorded at the same time, so a chunk can only be read whole: saving a
 * minute of it only downloads the chunks that minute falls in.
 */
import { isKeyframe, ParameterSetCache } from './codec'
import VideoFrameStream, { scanParameterSets, UNDECODABLE_FRAMES_BEFORE_SKIP } from './frame-stream'
import {
  AnnexBFrame, clampSampleDuration, Mp4FileStream, probeDecoderInfo, VideoDecoderInfo,
} from './mux'
import { McapVideoRecording } from './player'
import { VideoTrack } from './video-track'

export interface Mp4ExportProgress {
  seconds: number
  durationSeconds: number
  bytes: number
}

export interface Mp4ExportRange {
  startSeconds: number
  endSeconds: number
}

export interface Mp4ExportOptions {
  range?: Mp4ExportRange
  onProgress?: (progress: Mp4ExportProgress) => void
  signal?: AbortSignal
}

function abortError(): Error {
  const error = new Error('The export was cancelled.')
  error.name = 'AbortError'
  return error
}

interface HeldSample {
  data: Uint8Array
  logTime: bigint
  isKeyframe: boolean
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
  if (startSeconds > 0) {
    await stream.seekToKeyframe(startSeconds, signal)
  } else {
    stream.seekToStart()
  }
  const endLogTime = range && Number.isFinite(range.endSeconds) ? stream.toLogTime(range.endSeconds) : null

  const parameterSets = new ParameterSetCache()
  const parts: Blob[] = []
  let decoderInfo: VideoDecoderInfo | null = null
  let writer: Mp4FileStream | null = null
  let held: HeldSample | null = null
  let duration = 1 / 30
  let undecodable = 0
  let bytes = 0

  async function emit(sample: HeldSample, sampleDuration: number): Promise<void> {
    const frame: AnnexBFrame = {
      data: sample.data,
      timestamp: Math.max(0, stream.toSeconds(sample.logTime) - startSeconds),
      duration: sampleDuration,
      isKeyframe: sample.isKeyframe,
    }
    if (!writer && decoderInfo) {
      writer = await Mp4FileStream.open(decoderInfo, (data) => {
        parts.push(new Blob([data]))
        bytes += data.byteLength
      })
    }
    await writer?.add(frame)
    onProgress?.({
      seconds: Math.max(0, stream.toSeconds(sample.logTime) - startSeconds),
      durationSeconds: Math.max(endSeconds - startSeconds, 0),
      bytes,
    })
  }

  for (;;) {
    if (signal?.aborted) {
      throw abortError()
    }
    // eslint-disable-next-line no-await-in-loop
    const frame = await stream.next(signal)
    if (!frame) {
      break
    }
    if (endLogTime !== null && frame.logTime > endLogTime) {
      if (held) {
        // eslint-disable-next-line no-await-in-loop
        await emit(held, clampSampleDuration(Number(frame.logTime - held.logTime) / 1e9))
        held = null
      }
      break
    }

    const annexB = parameterSets.withParameterSets(frame.data, frame.format)
    const keyframe = isKeyframe(annexB, frame.format)
    if (!decoderInfo) {
      if (!keyframe) {
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
      // eslint-disable-next-line no-await-in-loop
      decoderInfo = await probeDecoderInfo(frame.format, parameterSets.withParameterSets(annexB, frame.format))
    }

    if (held) {
      duration = clampSampleDuration(Number(frame.logTime - held.logTime) / 1e9)
      // eslint-disable-next-line no-await-in-loop
      await emit(held, duration)
    }
    held = { data: annexB, logTime: frame.logTime, isKeyframe: keyframe }
  }

  if (!decoderInfo || !held && !writer) {
    throw new Error(range
      ? 'The selected part of this video stream holds no keyframe, so there is nothing that can be saved.'
      : 'This video stream holds no keyframe, so there is nothing that can be saved.')
  }
  if (held) {
    await emit(held, duration)
  }
  await writer?.finalize()
  return new Blob(parts, { type: 'video/mp4' })
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
