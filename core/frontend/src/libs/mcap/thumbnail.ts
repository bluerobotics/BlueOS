/**
 * Builds a JPEG preview of an MCAP video stream in the browser.
 *
 * The same range-request + fragmented-MP4 path the player uses feeds a single keyframe into Media
 * Source Extensions. That keeps the work on the browser's hardware decoder and works over plain
 * HTTP, where WebCodecs is not available.
 */
import {
  ParameterSetCache, toMp4Sample, VideoFormat,
} from './codec'
import VideoFrameStream, { scanParameterSets, UNDECODABLE_FRAMES_BEFORE_SKIP } from './frame-stream'
import { buildFragment, buildInitSegment, MINIMUM_SAMPLE_DURATION_US } from './mp4'
import { openMcapVideoRecording } from './player'
import { McapIndexedReader } from './reader'
import { VideoTrack } from './video-track'

const DEFAULT_TARGET_WIDTH = 320
const DEFAULT_QUALITY = 0.85
/** Where in the recording to look for a representative frame, matching the old on-vehicle grab. */
const PREVIEW_POSITION = 0.5
const FRAME_WAIT_MS = 10_000
/** Frames to inspect before giving up on finding a keyframe near the preview position. */
const MAX_PREVIEW_FRAMES = 240

export interface McapThumbnailOptions {
  signal?: AbortSignal
  /** Longest edge of the JPEG, keeping the original aspect ratio. */
  targetWidth?: number
  /** JPEG quality from 0 to 1. */
  quality?: number
}

function waitForSourceOpen(mediaSource: MediaSource, signal?: AbortSignal): Promise<void> {
  if (mediaSource.readyState === 'open') {
    return Promise.resolve()
  }
  return new Promise((resolve, reject) => {
    function onAbort(): void {
      cleanup()
      reject(signal?.reason ?? new Error('Thumbnail extraction was cancelled.'))
    }
    function onOpen(): void {
      cleanup()
      resolve()
    }
    function cleanup(): void {
      mediaSource.removeEventListener('sourceopen', onOpen)
      signal?.removeEventListener('abort', onAbort)
    }
    mediaSource.addEventListener('sourceopen', onOpen)
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

function appendBuffer(sourceBuffer: SourceBuffer, data: Uint8Array, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    function onAbort(): void {
      cleanup()
      reject(signal?.reason ?? new Error('Thumbnail extraction was cancelled.'))
    }
    function onUpdate(): void {
      cleanup()
      resolve()
    }
    function onError(): void {
      cleanup()
      reject(new Error('The browser refused the thumbnail media.'))
    }
    function cleanup(): void {
      sourceBuffer.removeEventListener('updateend', onUpdate)
      sourceBuffer.removeEventListener('error', onError)
      signal?.removeEventListener('abort', onAbort)
    }
    sourceBuffer.addEventListener('updateend', onUpdate)
    sourceBuffer.addEventListener('error', onError)
    signal?.addEventListener('abort', onAbort, { once: true })
    try {
      sourceBuffer.appendBuffer(data)
    } catch (error) {
      cleanup()
      reject(error)
    }
  })
}

function waitForVideoFrame(video: HTMLVideoElement, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup()
      reject(new Error('Timed out waiting for a thumbnail frame.'))
    }, FRAME_WAIT_MS)
    function onAbort(): void {
      cleanup()
      reject(signal?.reason ?? new Error('Thumbnail extraction was cancelled.'))
    }
    function done(): void {
      cleanup()
      resolve()
    }
    function cleanup(): void {
      window.clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
    }
    signal?.addEventListener('abort', onAbort, { once: true })
    if ('requestVideoFrameCallback' in video) {
      const frameVideo = video as HTMLVideoElement & {
        requestVideoFrameCallback: (callback: () => void) => number
      }
      frameVideo.requestVideoFrameCallback(() => done())
    } else {
      video.addEventListener('loadeddata', () => done(), { once: true })
    }
    video.play().catch(() => undefined)
  })
}

function canvasToJpeg(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob)
        return
      }
      reject(new Error('Failed to encode the thumbnail as JPEG.'))
    }, 'image/jpeg', quality)
  })
}

async function readPreviewKeyframe(
  reader: McapIndexedReader,
  stream: VideoFrameStream,
  track: VideoTrack,
  durationSeconds: number,
  parameterSets: ParameterSetCache,
  signal?: AbortSignal,
): Promise<{ format: VideoFormat, data: Uint8Array }> {
  const targetSeconds = durationSeconds > 0 ? durationSeconds * PREVIEW_POSITION : 0
  if (targetSeconds > 0) {
    await stream.seekToKeyframe(targetSeconds, signal)
  } else {
    stream.seekToStart()
  }

  let skipped = 0
  for (let index = 0; index < MAX_PREVIEW_FRAMES; index += 1) {
    // eslint-disable-next-line no-await-in-loop
    const frame = await stream.next(signal)
    if (!frame) {
      break
    }
    parameterSets.observeFrame(frame.data, frame.format)
    const sample = toMp4Sample(frame.data, frame.format, parameterSets)
    if (sample.data.length === 0) {
      continue
    }
    if (!sample.isKeyframe) {
      skipped += 1
      if (skipped >= UNDECODABLE_FRAMES_BEFORE_SKIP) {
        skipped = 0
        // eslint-disable-next-line no-await-in-loop
        await stream.skipToKeyframeHint(signal)
      }
      continue
    }
    if (!parameterSets.complete) {
      // eslint-disable-next-line no-await-in-loop
      await scanParameterSets(reader, track, parameterSets, signal)
    }
    return { format: frame.format, data: frame.data }
  }
  throw new Error('This video stream holds no keyframe, so there is nothing to preview.')
}

/**
 * Downloads one keyframe from the middle of the recording and captures it as a JPEG.
 * Returns null when the browser cannot decode the stream or the recording has no video.
 */
export async function extractMcapThumbnail(
  url: string,
  options: McapThumbnailOptions = {},
): Promise<Blob | null> {
  const { signal, targetWidth = DEFAULT_TARGET_WIDTH, quality = DEFAULT_QUALITY } = options
  if (typeof window === 'undefined' || !('MediaSource' in window)) {
    return null
  }

  const recording = await openMcapVideoRecording(url, signal)
  const track = [...recording.tracks]
    .filter((candidate) => candidate.frameCount > 0)
    .sort((left, right) => {
      const fakeScore = (name: string): number => (/fake/i.test(name) ? 1 : 0)
      return fakeScore(left.name) - fakeScore(right.name) || right.frameCount - left.frameCount
    })[0]
  if (!track) {
    return null
  }

  const stream = new VideoFrameStream(recording.reader, track)
  const parameterSets = new ParameterSetCache()
  const keyframe = await readPreviewKeyframe(
    recording.reader,
    stream,
    track,
    recording.durationSeconds,
    parameterSets,
    signal,
  )
  if (!parameterSets.complete) {
    await scanParameterSets(recording.reader, track, parameterSets, signal)
  }
  const config = parameterSets.buildConfig(keyframe.format)
  if (!config) {
    throw new Error(`This ${keyframe.format.toUpperCase()} stream was recorded without the parameter`
      + ' sets needed to decode it, so no preview can be made.')
  }

  const mime = `video/mp4; codecs="${config.codec}"`
  if (!MediaSource.isTypeSupported(mime)) {
    return null
  }

  const sample = toMp4Sample(keyframe.data, keyframe.format, parameterSets)
  const mediaSource = new MediaSource()
  const objectUrl = URL.createObjectURL(mediaSource)
  const video = document.createElement('video')
  video.muted = true
  video.playsInline = true
  video.preload = 'auto'
  video.src = objectUrl

  try {
    await waitForSourceOpen(mediaSource, signal)
    const sourceBuffer = mediaSource.addSourceBuffer(mime)
    sourceBuffer.mode = 'segments'
    await appendBuffer(sourceBuffer, buildInitSegment(config), signal)
    await appendBuffer(
      sourceBuffer,
      buildFragment([{ ...sample, duration: Math.max(MINIMUM_SAMPLE_DURATION_US, 33_333) }], 0, 1),
      signal,
    )
    if (mediaSource.readyState === 'open') {
      mediaSource.endOfStream()
    }
    video.currentTime = 0

    await waitForVideoFrame(video, signal)

    const scale = Math.min(1, targetWidth / Math.max(1, config.width))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(config.width * scale))
    canvas.height = Math.max(1, Math.round(config.height * scale))
    const context = canvas.getContext('2d')
    if (!context) {
      throw new Error('Failed to create a canvas for the thumbnail.')
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    return await canvasToJpeg(canvas, quality)
  } finally {
    video.pause()
    video.removeAttribute('src')
    video.load()
    URL.revokeObjectURL(objectUrl)
  }
}
