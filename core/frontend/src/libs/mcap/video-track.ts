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

export interface TimeRange {
  start: number
  end: number
}

export interface VideoTrack {
  channelId: number
  topic: string
  /** Stream name as configured in the video manager, derived from `video/<name>/stream`. */
  name: string
  frameCount: number
  /** Seconds from the start of the recording where this stream has frames. */
  coverage: TimeRange[]
}

/** Adjacent chunks closer than this are treated as one stretch of video. */
const COVERAGE_MERGE_SECONDS = 2

export function mergeTimeRanges(ranges: TimeRange[]): TimeRange[] {
  if (ranges.length === 0) {
    return []
  }
  const ordered = [...ranges].sort((left, right) => left.start - right.start)
  const merged: TimeRange[] = [{ ...ordered[0] }]
  for (const range of ordered.slice(1)) {
    const last = merged[merged.length - 1]
    if (range.start <= last.end + COVERAGE_MERGE_SECONDS) {
      last.end = Math.max(last.end, range.end)
    } else {
      merged.push({ ...range })
    }
  }
  return merged
}

export function timeRangesCover(ranges: TimeRange[], seconds: number): boolean {
  return ranges.some((range) => seconds >= range.start && seconds <= range.end)
}

export function coverageForChannel(reader: McapIndexedReader, channelId: number): TimeRange[] {
  const origin = reader.summary.startTime
  const ranges: TimeRange[] = []
  for (const chunk of reader.summary.chunkIndexes) {
    if (chunk.channelIds.length > 0 && !chunk.channelIds.includes(channelId)) {
      continue
    }
    ranges.push({
      start: Number(chunk.startTime - origin) / 1e9,
      end: Number(chunk.endTime - origin) / 1e9,
    })
  }
  const merged = mergeTimeRanges(ranges)
  if (merged.length > 0) {
    return merged
  }
  if ((reader.summary.messageCountByChannel.get(channelId) ?? 0n) <= 0n) {
    return []
  }
  const duration = Number(reader.summary.endTime - origin) / 1e9
  return duration > 0 ? [{ start: 0, end: duration }] : []
}

export interface VideoFrame {
  /** MCAP log time in nanoseconds, which is also the time base used by the chunk index. */
  logTime: bigint
  /** Recorder counter for this channel. Gaps mean frames that never reached the recording. */
  sequence: number
  format: VideoFormat
  data: Uint8Array
}

interface CompressedVideoMessage {
  data: Uint8Array
  format: string
  sec?: number
  nanosec?: number
}

export function parseCompressedVideo(
  messageReader: MessageReader,
  bytes: Uint8Array,
): { data: Uint8Array, format: VideoFormat, timestampSeconds: number } {
  const message = messageReader.readMessage(bytes) as CompressedVideoMessage
  if (!SUPPORTED_FORMATS.includes(message.format as VideoFormat)) {
    throw new Error(
      `Unsupported video format '${message.format}'. Only ${SUPPORTED_FORMATS.join(' and ')} can be played.`,
    )
  }
  return {
    data: message.data,
    format: message.format as VideoFormat,
    timestampSeconds: (message.sec ?? 0) + (message.nanosec ?? 0) / 1e9,
  }
}

export function listVideoTracks(reader: McapIndexedReader): VideoTrack[] {
  return reader.channelsBySchemaName(COMPRESSED_VIDEO_SCHEMA).map((channel) => ({
    channelId: channel.id,
    topic: channel.topic,
    name: channel.topic.replace(/^video\//, '').replace(/\/stream$/, ''),
    frameCount: Number(reader.summary.messageCountByChannel.get(channel.id) ?? 0n),
    coverage: coverageForChannel(reader, channel.id),
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
    const parsed = parseCompressedVideo(this.messageReader, message.data)
    return {
      logTime: message.logTime, sequence: message.sequence, format: parsed.format, data: parsed.data,
    }
  }
}
