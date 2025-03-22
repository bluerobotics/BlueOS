import {
  Device, FrameInterval, StreamStatus, VideoEncodeType,
} from '@/types/video'

export function video_encode_text(encode?: VideoEncodeType): string {
  if (encode === undefined) {
    return 'Unknown encode'
  }

  if (typeof encode === 'object' && 'UNKNOWN' in encode) {
    return `Unknown encode: ${encode.UNKNOWN}`
  }

  return encode
}

export function video_dimension_text(height?: number, width?: number): string {
  if (height === undefined || width === undefined || width === 0 || height === 0) {
    return 'Unknown size'
  }
  return `${width} x ${height} px`
}

export function video_framerate_text(frame_interval?: FrameInterval): string {
  if (frame_interval === undefined || frame_interval.denominator === 0 || frame_interval.numerator === 0) {
    return 'Unknown fps'
  }
  const framerate = frame_interval.denominator / frame_interval.numerator
  return `${framerate} fps`
}

export function video_dimension_framerate_text(
  height?: number,
  width?: number,
  frame_interval?: FrameInterval,
): string {
  return `${video_dimension_text(height, width)} @ ${video_framerate_text(frame_interval)}`
}

export function available_streams_from_device(available_streams: StreamStatus[], device: Device): StreamStatus[] {
  return available_streams.filter((stream) => {
    if ('Gst' in stream.video_and_stream.video_source) {
      return stream.video_and_stream.video_source.Gst.source.Fake === device.source
    }
    if ('Local' in stream.video_and_stream.video_source) {
      return stream.video_and_stream.video_source.Local.device_path === device.source
    }
    if ('Redirect' in stream.video_and_stream.video_source) {
      return stream.video_and_stream.video_source.Redirect.source.Redirect === device.source
    }
    if ('Onvif' in stream.video_and_stream.video_source) {
      return stream.video_and_stream.video_source.Onvif.source.Onvif === device.source
    }
    return false
  })
}
