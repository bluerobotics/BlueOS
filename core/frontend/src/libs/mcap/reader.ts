/**
 * Indexed MCAP reader over HTTP range requests, using @mcap/core to parse records.
 *
 * @mcap/core McapIndexedReader.Initialize reads the whole summary in one shot
 * (`readable.read(dataEndOffset, footerOffset - dataEndOffset)`), with a comment that avoiding
 * that blob is a future optimization. This open() is that optimization: SummaryOffset locates
 * Schema/Channel/Statistics (tens of kilobytes), and ChunkIndex records load in windows as
 * playback needs them. After this is proven against vehicle recordings, the same split belongs
 * upstream in foxglove/mcap.
 */
/* eslint-disable max-classes-per-file */
import type {
  Channel as McapChannelRecord,
  ChunkIndex as McapChunkIndexRecord,
  DecompressHandlers,
  Schema as McapSchemaRecord,
  TypedMcapRecord,
} from '@mcap/core'
import {
  McapRecordBuilder,
  McapStreamReader,
  Opcode,
} from '@mcap/core'
import { decompress as zstdDecompress } from 'fzstd'

import { ByteSource } from './source'

const MAGIC_SIZE = 8
const FOOTER_RECORD_SIZE = 29
const TAIL_READ_SIZE = 4096
/**
 * Bytes of chunk index to fetch at a time. The index costs a bit over half a kilobyte per chunk, so
 * a window covers a few minutes of video: enough to start watching without paying for the megabytes
 * that indexing a whole hour long recording would cost.
 */
const CHUNK_INDEX_WINDOW_SIZE = 256 * 1024
/**
 * Decompressed chunk bytes to keep around. A chunk holds every channel recorded in its time span, so
 * caching lets all the video streams of a recording play from a single download. The limit only has
 * to cover the lag between the stream that is furthest ahead and the one furthest behind.
 */
const CHUNK_CACHE_LIMIT_BYTES = 32 * 1024 * 1024

const METADATA_OPCODES = [Opcode.SCHEMA, Opcode.CHANNEL, Opcode.STATISTICS]

/** opcode + u64 length + channel_id + sequence + log_time + publish_time */
const MESSAGE_HEADER_SIZE = 31

const DECOMPRESS_HANDLERS: DecompressHandlers = {
  zstd: (buffer: Uint8Array, size: bigint): Uint8Array => zstdDecompress(
    buffer,
    Number(size) > 0 ? new Uint8Array(Number(size)) : undefined,
  ),
}

export class McapNeedsRepairError extends Error {}

interface SummaryGroup {
  start: number
  length: number
}

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
  messageIndexLength: number
}

export interface McapMessageEntry {
  logTime: bigint
  size: number
}

export interface McapOpenOptions {
  metadataOnly?: boolean
  signal?: AbortSignal
}

export interface McapMessage {
  channelId: number
  sequence: number
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

function abortError(): Error {
  const error = new Error('The read was aborted.')
  error.name = 'AbortError'
  return error
}

function whileWaiting<T>(work: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) {
    return work
  }
  if (signal.aborted) {
    return Promise.reject(abortError())
  }
  return new Promise<T>((resolve, reject) => {
    function onAbort(): void {
      reject(abortError())
    }
    signal.addEventListener('abort', onAbort, { once: true })
    work.then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort))
  })
}

function parseRecords(data: Uint8Array): { records: TypedMcapRecord[], consumed: number } {
  const stream = new McapStreamReader({ noMagicPrefix: true, validateCrcs: false })
  stream.append(data)
  const records: TypedMcapRecord[] = []
  for (let record = stream.nextRecord(); record; record = stream.nextRecord()) {
    records.push(record)
  }
  return { records, consumed: data.byteLength - stream.bytesRemaining() }
}

function toChunkIndex(record: McapChunkIndexRecord): McapChunkIndex {
  return {
    startTime: record.messageStartTime,
    endTime: record.messageEndTime,
    offset: Number(record.chunkStartOffset),
    length: Number(record.chunkLength),
    compression: record.compression,
    compressedSize: Number(record.compressedSize),
    uncompressedSize: Number(record.uncompressedSize),
    channelIds: [...record.messageIndexOffsets.keys()],
    messageIndexLength: Number(record.messageIndexLength),
  }
}

function toSchema(record: McapSchemaRecord): McapSchema {
  return {
    id: record.id, name: record.name, encoding: record.encoding, data: record.data,
  }
}

function toChannel(record: McapChannelRecord): McapChannel {
  return {
    id: record.id, schemaId: record.schemaId, topic: record.topic, messageEncoding: record.messageEncoding,
  }
}

export class McapIndexedReader {
  private chunkIndexCursor: number | null

  private pendingLoad: Promise<boolean> = Promise.resolve(false)

  private chunkCache = new Map<number, Uint8Array>()

  private chunkCacheBytes = 0

  private chunkLoads = new Map<number, Promise<Uint8Array>>()

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
    const footerBytes = tail.subarray(tail.length - MAGIC_SIZE - FOOTER_RECORD_SIZE)
    let footer: Extract<TypedMcapRecord, { type: 'Footer' }> | undefined
    try {
      footer = parseRecords(footerBytes).records.find(
        (record): record is Extract<TypedMcapRecord, { type: 'Footer' }> => record.type === 'Footer',
      )
    } catch {
      footer = undefined
    }
    if (!footer) {
      throw new McapNeedsRepairError('This recording was cut short before it could be closed.')
    }
    if (footer.summaryStart === 0n) {
      throw new McapNeedsRepairError('This recording holds no index, so nothing can be read out of it.')
    }

    const summaryStart = Number(footer.summaryStart)
    const summaryOffsetStart = Number(footer.summaryOffsetStart)
    const summaryEnd = size - MAGIC_SIZE - FOOTER_RECORD_SIZE
    const groups = await McapIndexedReader
      .readSummaryOffsets(source, summaryOffsetStart, summaryEnd, tail, size, signal)
    const statistics = groups?.get(Opcode.STATISTICS)
    const chunkIndex = groups?.get(Opcode.CHUNK_INDEX)

    if (!groups || !statistics || !chunkIndex) {
      const data = await source.read(summaryStart, summaryEnd - summaryStart, signal)
      return new McapIndexedReader(source, McapIndexedReader.summaryFrom(parseRecords(data).records, size), null)
    }

    const wanted = [...groups.entries()]
      .filter(([opcode]) => METADATA_OPCODES.includes(opcode))
      .map(([, group]) => group)
    const metadata = await McapIndexedReader.readGroups(source, wanted, signal)
    const summary = McapIndexedReader.summaryFrom(parseRecords(metadata).records, size)
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
    for (const record of parseRecords(offsetsData).records) {
      if (record.type !== 'SummaryOffset' || record.groupLength === 0n) {
        continue
      }
      groups.set(record.groupOpcode, { start: Number(record.groupStart), length: Number(record.groupLength) })
    }
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

  private static summaryFrom(records: TypedMcapRecord[], size: number): McapSummary {
    const schemas = new Map<number, McapSchema>()
    const channels = new Map<number, McapChannel>()
    const chunkIndexes: McapChunkIndex[] = []
    const messageCountByChannel = new Map<number, bigint>()
    let startTime = 0n
    let endTime = 0n

    for (const record of records) {
      switch (record.type) {
        case 'Schema':
          schemas.set(record.id, toSchema(record))
          break
        case 'Channel':
          channels.set(record.id, toChannel(record))
          break
        case 'ChunkIndex':
          chunkIndexes.push(toChunkIndex(record))
          break
        case 'Statistics':
          startTime = record.messageStartTime
          endTime = record.messageEndTime
          for (const [channelId, count] of record.channelMessageCounts) {
            messageCountByChannel.set(channelId, count)
          }
          break
        default:
          break
      }
    }

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

  loadMoreChunkIndexes(signal?: AbortSignal): Promise<boolean> {
    this.pendingLoad = this.pendingLoad
      .catch(() => false)
      .then(() => this.readNextChunkIndexWindow(signal))
    return this.pendingLoad
  }

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
    const { records, consumed } = parseRecords(data)
    if (consumed === 0) {
      throw new Error('Chunk index record does not fit in a read window.')
    }

    for (const record of records) {
      if (record.type === 'ChunkIndex') {
        this.summary.chunkIndexes.push(toChunkIndex(record))
      }
    }
    this.chunkIndexCursor = cursor + consumed < end ? cursor + consumed : null
    return true
  }

  channelsBySchemaName(schemaName: string): McapChannel[] {
    return [...this.summary.channels.values()]
      .filter((channel) => this.summary.schemas.get(channel.schemaId)?.name === schemaName)
      .sort((left, right) => left.topic.localeCompare(right.topic))
  }

  chunkIndexesForChannel(channelId: number): number[] {
    return this.summary.chunkIndexes
      .map((chunk, index) => ({ chunk, index }))
      .filter(({ chunk }) => chunk.channelIds.length === 0 || chunk.channelIds.includes(channelId))
      .map(({ index }) => index)
  }

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
    for (const record of parseRecords(data).records) {
      if (record.type !== 'MessageIndex') {
        continue
      }
      for (const [logTime, offset] of record.records) {
        const offsetNumber = Number(offset)
        allOffsets.push(offsetNumber)
        if (record.channelId === channelId) {
          channelOffsets.push({ logTime, offset: offsetNumber })
        }
      }
    }

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
    const data = await this.readChunkData(chunkIndex, signal)
    const builder = new McapRecordBuilder()
    for (const channel of this.summary.channels.values()) {
      builder.writeChannel({
        id: channel.id,
        schemaId: channel.schemaId,
        topic: channel.topic,
        messageEncoding: channel.messageEncoding,
        metadata: new Map(),
      })
    }
    const stream = new McapStreamReader({ noMagicPrefix: true, validateCrcs: false })
    stream.append(builder.buffer)
    stream.append(data)

    const messages: McapMessage[] = []
    for (let record = stream.nextRecord(); record; record = stream.nextRecord()) {
      if (record.type !== 'Message' || record.channelId !== channelId) {
        continue
      }
      messages.push({
        channelId: record.channelId, sequence: record.sequence, logTime: record.logTime, data: record.data,
      })
    }
    messages.sort((left, right) => Number(left.logTime - right.logTime))
    return messages
  }

  private async readChunkData(chunkIndex: number, signal?: AbortSignal): Promise<Uint8Array> {
    const cached = this.chunkCache.get(chunkIndex)
    if (cached) {
      this.chunkCache.delete(chunkIndex)
      this.chunkCache.set(chunkIndex, cached)
      return cached
    }

    let load = this.chunkLoads.get(chunkIndex)
    if (!load) {
      load = this.downloadChunk(chunkIndex)
        .then((data) => {
          this.cacheChunk(chunkIndex, data)
          return data
        })
        .finally(() => this.chunkLoads.delete(chunkIndex))
      this.chunkLoads.set(chunkIndex, load)
    }
    return whileWaiting(load, signal)
  }

  private async downloadChunk(chunkIndex: number): Promise<Uint8Array> {
    const index = this.summary.chunkIndexes[chunkIndex]
    if (!index) {
      throw new Error(`Chunk ${chunkIndex} is out of range.`)
    }

    const record = await this.source.read(index.offset, index.length)
    const stream = new McapStreamReader({
      includeChunks: true, noMagicPrefix: true, validateCrcs: false,
    })
    stream.append(record)
    const chunk = stream.nextRecord()
    if (!chunk || chunk.type !== 'Chunk') {
      throw new Error(`Expected a chunk record at offset ${index.offset}.`)
    }
    if (chunk.compression === '') {
      return chunk.records
    }
    const decompress = DECOMPRESS_HANDLERS[chunk.compression]
    if (!decompress) {
      throw new Error(`Unsupported MCAP chunk compression: '${chunk.compression}'.`)
    }
    return decompress(chunk.records, chunk.uncompressedSize)
  }

  private cacheChunk(chunkIndex: number, data: Uint8Array): void {
    this.chunkCache.set(chunkIndex, data)
    this.chunkCacheBytes += data.length
    for (const [key, value] of this.chunkCache) {
      if (this.chunkCacheBytes <= CHUNK_CACHE_LIMIT_BYTES || key === chunkIndex) {
        break
      }
      this.chunkCache.delete(key)
      this.chunkCacheBytes -= value.length
    }
  }
}
