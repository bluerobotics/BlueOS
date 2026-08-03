/**
 * Minimal MCAP reader designed for random access over HTTP range requests.
 *
 * Only the records needed to locate and decode video messages are parsed. The file index (footer +
 * summary section) lives at the end of the file, so opening a multi-gigabyte recording costs a few
 * tens of kilobytes and every seek afterwards downloads just the chunks that overlap the requested
 * time range.
 */
import { decompress as zstdDecompress } from 'fzstd'

import { forEachRecord, RecordReader } from './record-reader'
import { ByteSource } from './source'

const MAGIC = [0x89, 0x4d, 0x43, 0x41, 0x50, 0x30, 0x0d, 0x0a]
const MAGIC_SIZE = MAGIC.length
const FOOTER_RECORD_SIZE = 29 // opcode + u64 length + summary_start + summary_offset_start + crc
const TAIL_READ_SIZE = 4096
/**
 * Bytes of chunk index to fetch at a time. The index costs a bit over half a kilobyte per chunk, so
 * a window covers a few minutes of video: enough to start watching without paying for the megabytes
 * that indexing a whole hour long recording would cost.
 */
const CHUNK_INDEX_WINDOW_SIZE = 256 * 1024

enum Opcode {
  SCHEMA = 0x03,
  CHANNEL = 0x04,
  MESSAGE = 0x05,
  CHUNK = 0x06,
  MESSAGE_INDEX = 0x07,
  CHUNK_INDEX = 0x08,
  STATISTICS = 0x0b,
  SUMMARY_OFFSET = 0x0e,
}

/** Records describing what a recording contains, as opposed to where its data lives. */
const METADATA_OPCODES = [Opcode.SCHEMA, Opcode.CHANNEL, Opcode.STATISTICS]

interface SummaryGroup {
  start: number
  length: number
}

/** opcode + u64 length + channel_id + sequence + log_time + publish_time */
const MESSAGE_HEADER_SIZE = 31

export interface McapSchema {
  id: number
  name: string
  encoding: string
  data: Uint8Array
}

export interface McapChannel {
  id: number
  schemaId: number
  topic: string
  messageEncoding: string
}

export interface McapChunkIndex {
  startTime: bigint
  endTime: bigint
  offset: number
  length: number
  compression: string
  compressedSize: number
  uncompressedSize: number
  channelIds: number[]
  /** Total size of the message index records that follow the chunk. */
  messageIndexLength: number
}

/** Log time and size of a single message, derived from the message index alone. */
export interface McapMessageEntry {
  logTime: bigint
  size: number
}

export interface McapOpenOptions {
  /** Skip the chunk index, which is only needed to seek and read messages. */
  metadataOnly?: boolean
  signal?: AbortSignal
}

export interface McapMessage {
  channelId: number
  logTime: bigint
  data: Uint8Array
}

export interface McapSummary {
  size: number
  startTime: bigint
  endTime: bigint
  schemas: Map<number, McapSchema>
  channels: Map<number, McapChannel>
  chunkIndexes: McapChunkIndex[]
  messageCountByChannel: Map<number, bigint>
}

function hasMagic(bytes: Uint8Array, offset: number): boolean {
  return MAGIC.every((byte, index) => bytes[offset + index] === byte)
}

function decompressChunk(compression: string, compressed: Uint8Array, uncompressedSize: number): Uint8Array {
  switch (compression) {
    case '':
      return compressed
    case 'zstd':
      return zstdDecompress(compressed, uncompressedSize > 0 ? new Uint8Array(uncompressedSize) : undefined)
    default:
      throw new Error(`Unsupported MCAP chunk compression: '${compression}'.`)
  }
}

export class McapIndexedReader {
  /** Next unread byte of the chunk index group, or null when the whole index is already loaded. */
  private chunkIndexCursor: number | null

  private pendingLoad: Promise<boolean> = Promise.resolve(false)

  private constructor(
    public readonly source: ByteSource,
    public readonly summary: McapSummary,
    private chunkIndexGroup: SummaryGroup | null,
  ) {
    this.chunkIndexCursor = chunkIndexGroup?.start ?? null
  }

  /**
   * Reads the index of a recording. Schemas, channels and statistics are fetched up front, which
   * costs a few tens of kilobytes whatever the recording size, while the chunk index is loaded in
   * windows as playback needs it. With `metadataOnly` the chunk index is never read, at the price of
   * not being able to read messages.
   */
  static async open(source: ByteSource, options: McapOpenOptions = {}): Promise<McapIndexedReader> {
    const { metadataOnly = false, signal } = options
    const size = await source.size(signal)
    if (size < MAGIC_SIZE * 2 + FOOTER_RECORD_SIZE) {
      throw new Error('File is too small to be an MCAP recording.')
    }

    const tailSize = Math.min(TAIL_READ_SIZE, size)
    const tail = await source.read(size - tailSize, tailSize, signal)
    if (!hasMagic(tail, tail.length - MAGIC_SIZE)) {
      throw new Error('Not an MCAP file, or the recording was truncated before being closed.')
    }

    const footer = new RecordReader(tail, tail.length - MAGIC_SIZE - FOOTER_RECORD_SIZE)
    footer.uint8()
    footer.size()
    const summaryStart = Number(footer.uint64())
    const summaryOffsetStart = Number(footer.uint64())
    if (summaryStart === 0) {
      throw new Error('Recording has no index, so it cannot be streamed. It needs to be repaired first.')
    }

    const summaryEnd = size - MAGIC_SIZE - FOOTER_RECORD_SIZE
    const groups = await McapIndexedReader.readSummaryOffsets(source, summaryOffsetStart, summaryEnd, tail, size, signal)
    const statistics = groups?.get(Opcode.STATISTICS)
    const chunkIndex = groups?.get(Opcode.CHUNK_INDEX)

    // Statistics carry the time span of the recording. Without them, or without summary offsets to
    // locate the groups, the only way to learn what the recording holds is to read the summary whole.
    if (!groups || !statistics || !chunkIndex) {
      const data = await source.read(summaryStart, summaryEnd - summaryStart, signal)
      return new McapIndexedReader(source, McapIndexedReader.parseSummary(data, size), null)
    }

    const wanted = [...groups.entries()]
      .filter(([opcode]) => METADATA_OPCODES.includes(opcode))
      .map(([, group]) => group)
    const metadata = await McapIndexedReader.readGroups(source, wanted, signal)
    const summary = McapIndexedReader.parseSummary(metadata, size)
    return new McapIndexedReader(source, summary, metadataOnly ? null : chunkIndex)
  }

  /**
   * Locates the record groups of the summary section. Returns null for recordings written without a
   * summary offset section, in which case the caller has to read the summary whole.
   */
  private static async readSummaryOffsets(
    source: ByteSource,
    summaryOffsetStart: number,
    summaryEnd: number,
    tail: Uint8Array,
    size: number,
    signal?: AbortSignal,
  ): Promise<Map<number, SummaryGroup> | null> {
    if (summaryOffsetStart === 0) {
      return null
    }

    const tailOffset = size - tail.length
    const offsetsData = summaryOffsetStart >= tailOffset
      ? tail.subarray(summaryOffsetStart - tailOffset, summaryEnd - tailOffset)
      : await source.read(summaryOffsetStart, summaryEnd - summaryOffsetStart, signal)

    const groups = new Map<number, SummaryGroup>()
    forEachRecord(offsetsData, (opcode, reader) => {
      if (opcode !== Opcode.SUMMARY_OFFSET) {
        return
      }
      const groupOpcode = reader.uint8()
      const start = Number(reader.uint64())
      const length = Number(reader.uint64())
      if (length > 0) {
        groups.set(groupOpcode, { start, length })
      }
    })
    return groups.size > 0 ? groups : null
  }

  private static async readGroups(
    source: ByteSource,
    groups: SummaryGroup[],
    signal?: AbortSignal,
  ): Promise<Uint8Array> {
    const ordered = [...groups].sort((left, right) => left.start - right.start)
    const parts = await Promise.all(ordered.map((group) => source.read(group.start, group.length, signal)))
    const total = parts.reduce((sum, part) => sum + part.length, 0)
    const merged = new Uint8Array(total)
    let offset = 0
    for (const part of parts) {
      merged.set(part, offset)
      offset += part.length
    }
    return merged
  }

  private static parseChunkIndex(reader: RecordReader): McapChunkIndex {
    const startTime = reader.uint64()
    const endTime = reader.uint64()
    const offset = Number(reader.uint64())
    const length = Number(reader.uint64())
    const channelIds: number[] = []
    const mapEnd = reader.offset + reader.uint32()
    while (reader.offset < mapEnd) {
      channelIds.push(reader.uint16())
      reader.skip(8)
    }
    const messageIndexLength = Number(reader.uint64())
    return {
      startTime,
      endTime,
      offset,
      length,
      compression: reader.string(),
      compressedSize: Number(reader.uint64()),
      uncompressedSize: Number(reader.uint64()),
      channelIds,
      messageIndexLength,
    }
  }

  private static parseSummary(data: Uint8Array, size: number): McapSummary {
    const schemas = new Map<number, McapSchema>()
    const channels = new Map<number, McapChannel>()
    const chunkIndexes: McapChunkIndex[] = []
    const messageCountByChannel = new Map<number, bigint>()
    let startTime = 0n
    let endTime = 0n

    forEachRecord(data, (opcode, reader) => {
      switch (opcode) {
        case Opcode.SCHEMA: {
          const id = reader.uint16()
          const name = reader.string()
          const encoding = reader.string()
          schemas.set(id, {
            id, name, encoding, data: reader.bytes(reader.uint32()),
          })
          break
        }
        case Opcode.CHANNEL: {
          const id = reader.uint16()
          channels.set(id, {
            id, schemaId: reader.uint16(), topic: reader.string(), messageEncoding: reader.string(),
          })
          break
        }
        case Opcode.CHUNK_INDEX:
          chunkIndexes.push(McapIndexedReader.parseChunkIndex(reader))
          break
        case Opcode.STATISTICS: {
          reader.skip(8 + 2 + 4 + 4 + 4 + 4)
          startTime = reader.uint64()
          endTime = reader.uint64()
          const mapEnd = reader.offset + reader.uint32()
          while (reader.offset < mapEnd) {
            messageCountByChannel.set(reader.uint16(), reader.uint64())
          }
          break
        }
        default:
          break
      }
    })

    chunkIndexes.sort((left, right) => Number(left.startTime - right.startTime))
    if (startTime === 0n && chunkIndexes.length > 0) {
      startTime = chunkIndexes[0].startTime
      endTime = chunkIndexes[chunkIndexes.length - 1].endTime
    }

    return {
      size, startTime, endTime, schemas, channels, chunkIndexes, messageCountByChannel,
    }
  }

  get chunkIndexComplete(): boolean {
    return this.chunkIndexGroup === null || this.chunkIndexCursor === null
  }

  /**
   * Reads the next window of chunk index records. Calls are serialised so that a seek and a running
   * read cannot fetch the same window twice. Returns false once the whole index has been read.
   */
  loadMoreChunkIndexes(signal?: AbortSignal): Promise<boolean> {
    this.pendingLoad = this.pendingLoad
      .catch(() => false)
      .then(() => this.readNextChunkIndexWindow(signal))
    return this.pendingLoad
  }

  /** Reads chunk index records until the recording is covered up to the given time. */
  async loadChunkIndexesUntil(time: bigint, signal?: AbortSignal): Promise<void> {
    while (!this.chunkIndexComplete) {
      const last = this.summary.chunkIndexes[this.summary.chunkIndexes.length - 1]
      if (last && last.endTime >= time) {
        return
      }
      // eslint-disable-next-line no-await-in-loop
      if (!await this.loadMoreChunkIndexes(signal)) {
        return
      }
    }
  }

  private async readNextChunkIndexWindow(signal?: AbortSignal): Promise<boolean> {
    const group = this.chunkIndexGroup
    const cursor = this.chunkIndexCursor
    if (!group || cursor === null) {
      return false
    }

    const end = group.start + group.length
    const data = await this.source.read(cursor, Math.min(CHUNK_INDEX_WINDOW_SIZE, end - cursor), signal)
    const chunks: McapChunkIndex[] = []
    const consumed = forEachRecord(data, (opcode, reader) => {
      if (opcode === Opcode.CHUNK_INDEX) {
        chunks.push(McapIndexedReader.parseChunkIndex(reader))
      }
    })
    if (consumed === 0) {
      throw new Error('Chunk index record does not fit in a read window.')
    }

    // Chunk indexes are written in the order the chunks appear in the file, so appending keeps the
    // list sorted by time and, more importantly, keeps the position of every chunk stable.
    this.summary.chunkIndexes.push(...chunks)
    this.chunkIndexCursor = cursor + consumed < end ? cursor + consumed : null
    return true
  }

  channelsBySchemaName(schemaName: string): McapChannel[] {
    return [...this.summary.channels.values()]
      .filter((channel) => this.summary.schemas.get(channel.schemaId)?.name === schemaName)
      .sort((left, right) => left.topic.localeCompare(right.topic))
  }

  /** Indexes of the chunks holding messages for a channel, in time order. */
  chunkIndexesForChannel(channelId: number): number[] {
    return this.summary.chunkIndexes
      .map((chunk, index) => ({ chunk, index }))
      .filter(({ chunk }) => chunk.channelIds.length === 0 || chunk.channelIds.includes(channelId))
      .map(({ index }) => index)
  }

  /** First chunk that may contain a message at or after the given time. */
  findChunkIndexAtTime(channelId: number, time: bigint): number {
    const candidates = this.chunkIndexesForChannel(channelId)
    let result = candidates.length > 0 ? candidates[0] : 0
    for (const index of candidates) {
      if (this.summary.chunkIndexes[index].startTime > time) {
        break
      }
      result = index
    }
    return result
  }

  /**
   * Reads the message index that follows a chunk to obtain the log time and size of every message
   * of a channel, without downloading the chunk itself. A chunk of video costs hundreds of kilobytes
   * while its message index costs a few, which is what makes cheap keyframe lookup possible.
   */
  async readChunkMessageEntries(
    chunkIndex: number,
    channelId: number,
    signal?: AbortSignal,
  ): Promise<McapMessageEntry[] | null> {
    const index = this.summary.chunkIndexes[chunkIndex]
    if (!index || index.messageIndexLength === 0) {
      return null
    }

    const data = await this.source.read(index.offset + index.length, index.messageIndexLength, signal)
    const allOffsets: number[] = []
    const channelOffsets: { logTime: bigint, offset: number }[] = []
    forEachRecord(data, (opcode, reader) => {
      if (opcode !== Opcode.MESSAGE_INDEX) {
        return
      }
      const recordChannelId = reader.uint16()
      const arrayEnd = reader.offset + reader.uint32()
      while (reader.offset < arrayEnd) {
        const logTime = reader.uint64()
        const offset = Number(reader.uint64())
        allOffsets.push(offset)
        if (recordChannelId === channelId) {
          channelOffsets.push({ logTime, offset })
        }
      }
    })

    // A message ends where the next message of any channel begins.
    allOffsets.sort((left, right) => left - right)
    return channelOffsets.map(({ logTime, offset }) => {
      let low = 0
      let high = allOffsets.length
      while (low < high) {
        const middle = Math.floor((low + high) / 2)
        if (allOffsets[middle] <= offset) {
          low = middle + 1
        } else {
          high = middle
        }
      }
      const end = low < allOffsets.length ? allOffsets[low] : index.uncompressedSize
      return { logTime, size: Math.max(0, end - offset - MESSAGE_HEADER_SIZE) }
    }).sort((left, right) => Number(left.logTime - right.logTime))
  }

  async readChunkMessages(chunkIndex: number, channelId: number, signal?: AbortSignal): Promise<McapMessage[]> {
    const index = this.summary.chunkIndexes[chunkIndex]
    if (!index) {
      throw new Error(`Chunk ${chunkIndex} is out of range.`)
    }

    const record = await this.source.read(index.offset, index.length, signal)
    const reader = new RecordReader(record)
    if (reader.uint8() !== Opcode.CHUNK) {
      throw new Error(`Expected a chunk record at offset ${index.offset}.`)
    }
    reader.size()
    reader.skip(8 + 8) // message_start_time, message_end_time
    const uncompressedSize = reader.size()
    reader.skip(4) // uncompressed_crc
    const compression = reader.string()
    const compressed = reader.bytes(reader.size())
    const data = decompressChunk(compression, compressed, uncompressedSize)

    const messages: McapMessage[] = []
    forEachRecord(data, (opcode, message, end) => {
      if (opcode !== Opcode.MESSAGE || message.uint16() !== channelId) {
        return
      }
      message.skip(4) // sequence
      const logTime = message.uint64()
      message.skip(8) // publish_time
      messages.push({ channelId, logTime, data: message.bytes(end - message.offset) })
    })

    messages.sort((left, right) => Number(left.logTime - right.logTime))
    return messages
  }
}
