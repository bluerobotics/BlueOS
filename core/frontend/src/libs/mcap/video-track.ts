/** Discovery and decoding of `foxglove.CompressedVideo` streams stored in an MCAP recording. */
import { parse as parseMessageDefinition } from '@foxglove/rosmsg'
import { MessageReader } from '@foxglove/rosmsg2-serialization'

import { VideoFormat } from './codec'
import { McapChannel, McapIndexedReader, McapMessage } from './reader'

export const COMPRESSED_VIDEO_SCHEMA = 'foxglove.CompressedVideo'

const SUPPORTED_FORMATS: VideoFormat[] = ['h264', 'h265']

// The published schema refers to builtin_interfaces/Time, which is not included in the file. Since
// the CDR layout of that message is just the two fields, inlining them keeps the reader self
// contained.
const TIME_DEFINITION = /^\s*builtin_interfaces\/Time\s+timestamp\s*$/m
const INLINE_TIME = 'int32 sec\nuint32 nanosec'

export interface VideoTrack {
  channelId: number
  topic: string
  /** Stream name as configured in the video manager, derived from `video/<name>/stream`. */
  name: string
  frameCount: number
}

export interface VideoFrame {
  /** MCAP log time in nanoseconds, which is also the time base used by the chunk index. */
  logTime: bigint
  format: VideoFormat
  data: Uint8Array
}

interface CompressedVideoMessage {
  data: Uint8Array
  format: string
}

export function listVideoTracks(reader: McapIndexedReader): VideoTrack[] {
  return reader.channelsBySchemaName(COMPRESSED_VIDEO_SCHEMA).map((channel) => ({
    channelId: channel.id,
    topic: channel.topic,
    name: channel.topic.replace(/^video\//, '').replace(/\/stream$/, ''),
    frameCount: Number(reader.summary.messageCountByChannel.get(channel.id) ?? 0n),
  }))
}

export class VideoFrameDecoder {
  private constructor(private messageReader: MessageReader) {}

  static create(reader: McapIndexedReader, channel: McapChannel): VideoFrameDecoder {
    if (channel.messageEncoding !== 'cdr') {
      throw new Error(`Unsupported video message encoding: '${channel.messageEncoding}'.`)
    }
    const schema = reader.summary.schemas.get(channel.schemaId)
    if (!schema) {
      throw new Error(`Recording is missing the schema for ${channel.topic}.`)
    }
    const text = new TextDecoder().decode(schema.data).replace(TIME_DEFINITION, INLINE_TIME)
    return new VideoFrameDecoder(new MessageReader(parseMessageDefinition(text, { ros2: true })))
  }

  decode(message: McapMessage): VideoFrame {
    const { data, format } = this.messageReader.readMessage(message.data) as CompressedVideoMessage
    if (!SUPPORTED_FORMATS.includes(format as VideoFormat)) {
      throw new Error(`Unsupported video format '${format}'. Only ${SUPPORTED_FORMATS.join(' and ')} can be played.`)
    }
    return { logTime: message.logTime, format: format as VideoFormat, data }
  }
}
