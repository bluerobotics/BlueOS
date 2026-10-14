import { McapIndexedReader } from './reader'
import { COMPRESSED_VIDEO_SCHEMA } from './video-track'

export interface McapRecordingChannel {
  channelId: number
  topic: string
  schemaName: string
  messageEncoding: string
  messageCount: number
}

export function listMcapChannels(reader: McapIndexedReader): McapRecordingChannel[] {
  return [...reader.summary.channels.values()]
    .map((channel) => ({
      channelId: channel.id,
      topic: channel.topic,
      schemaName: reader.summary.schemas.get(channel.schemaId)?.name ?? '',
      messageEncoding: channel.messageEncoding,
      messageCount: Number(reader.summary.messageCountByChannel.get(channel.id) ?? 0n),
    }))
    .sort((left, right) => left.topic.localeCompare(right.topic))
}

export function isOpaqueByteChannel(channel: McapRecordingChannel): boolean {
  if (channel.schemaName === COMPRESSED_VIDEO_SCHEMA) {
    return true
  }
  if (channel.messageEncoding === 'octet-stream') {
    return true
  }
  return false
}

export function defaultSelectedChannelIds(channels: McapRecordingChannel[]): number[] {
  return channels.filter((channel) => !isOpaqueByteChannel(channel)).map((channel) => channel.channelId)
}
