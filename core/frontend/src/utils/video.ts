import { FrameInterval } from '@/types/video'

export function video_dimension_text(height: number, width: number): string {
  return `${width} x ${height} px`
}

export function video_framerate_text(frame_interval: FrameInterval): string {
  const framerate = frame_interval.denominator / frame_interval.numerator
  return `${framerate} fps`
}

export function video_dimension_framerate_text(height: number, width: number, frame_interval: FrameInterval): string {
  return `${video_dimension_text(height, width)} @ ${video_framerate_text(frame_interval)}`
}
