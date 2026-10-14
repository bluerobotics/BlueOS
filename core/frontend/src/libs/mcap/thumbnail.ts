/**
 * Builds a JPEG preview of an MCAP video stream in the browser.
 *
 * The same range-request + fragmented-MP4 path the player uses feeds a single keyframe into Media
 * Source Extensions. That keeps the work on the browser's hardware decoder and works over plain
 * HTTP, where WebCodecs is not available.
 */
import VideoFrameStream from './frame-stream'
import { DecodableFrameCursor } from './frames'
import { appendSourceBuffer, waitForSourceOpen } from './mse'
import { muxFragmentedMp4 } from './mux'
import { openMcapVideoRecording } from './player'

const DEFAULT_TARGET_WIDTH = 320
const DEFAULT_QUALITY = 0.85
const PREVIEW_POSITION = 0.5
const FRAME_WAIT_MS = 10_000
const MAX_PREVIEW_FRAMES = 240

export interface McapThumbnailOptions {
  signal?: AbortSignal
  targetWidth?: number
  quality?: number
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

  const recording = await openMcapVideoRecording(url, { signal })
  const track = [...recording.tracks]
    .filter((candidate) => candidate.frameCount > 0)
    .sort((left, right) => {
      function fakeScore(name: string): number {
        return /fake/i.test(name) ? 1 : 0
      }
      return fakeScore(left.name) - fakeScore(right.name) || right.frameCount - left.frameCount
    })[0]
  if (!track) {
    return null
  }

  const stream = new VideoFrameStream(recording.reader, track)
  const cursor = new DecodableFrameCursor(stream, recording.reader, track)
  const targetSeconds = recording.durationSeconds > 0 ? recording.durationSeconds * PREVIEW_POSITION : 0
  if (targetSeconds > 0) {
    await stream.seekToKeyframe(targetSeconds, signal)
  } else {
    stream.seekToStart()
  }
  const keyframe = await cursor.next(signal, MAX_PREVIEW_FRAMES)
  const info = cursor.decoderInfo
  if (!keyframe || !info) {
    throw new Error('This video stream holds no keyframe, so there is nothing to preview.')
  }
  const mime = `video/mp4; codecs="${info.codec}"`
  if (!MediaSource.isTypeSupported(mime)) {
    return null
  }

  const media = await muxFragmentedMp4([{
    data: keyframe.annexB, timestamp: 0, duration: 1 / 30, isKeyframe: true,
  }], info)

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
    await appendSourceBuffer(sourceBuffer, media, signal, 'The browser refused the thumbnail media.')
    if (mediaSource.readyState === 'open') {
      mediaSource.endOfStream()
    }
    video.currentTime = 0

    await waitForVideoFrame(video, signal)

    const scale = Math.min(1, targetWidth / Math.max(1, info.width))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(info.width * scale))
    canvas.height = Math.max(1, Math.round(info.height * scale))
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
