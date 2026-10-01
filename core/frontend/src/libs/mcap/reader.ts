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
  MCAP_MAGIC,
  McapStreamReader,
  Opcode,
} from '@mcap/core'
import { decompress as zstdDecompress } from 'fzstd'
import { decompress as lz4DecompressFrame, decompressBlock as lz4DecompressBlock } from 'lz4js'

import { whileWaiting } from './abort'
import { createProgressGate } from './progress'
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
/** Chunk index entries per vehicle index request; matches the recorder-extractor default. */
const SERVER_INDEX_PAGE_LIMIT = 2000
/**
 * Chunk bytes to spend naming channels while opening a recording. A channel is only described in the
 * chunk that first carried it, so every name costs a whole chunk download; the busiest channels are
 * resolved first because a video stream records orders of magnitude more messages than a log topic.
 * Whatever the budget does not reach stays unnamed until something asks for the whole topic list.
 */
const CHANNEL_NAMING_BUDGET_BYTES = 16 * 1024 * 1024

const METADATA_OPCODES = [Opcode.SCHEMA, Opcode.CHANNEL, Opcode.STATISTICS]

/** opcode + u64 length + channel_id + sequence + log_time + publish_time */
const MESSAGE_HEADER_SIZE = 31

/** LZ4 frame magic (little-endian 0x184D2204). Vehicle recordings write frames, not raw blocks. */
const LZ4_FRAME_MAGIC = [0x04, 0x22, 0x4d, 0x18]

function lz4Decompress(buffer: Uint8Array, size: bigint): Uint8Array {
  if (
    buffer.length >= LZ4_FRAME_MAGIC.length
    && LZ4_FRAME_MAGIC.every((byte, index) => buffer[index] === byte)
  ) {
    return lz4DecompressFrame(buffer, Number(size) > 0 ? Number(size) : undefined)
  }
  const output = new Uint8Array(Number(size))
  const written = lz4DecompressBlock(buffer, output, 0, buffer.byteLength, 0)
  return written === output.byteLength ? output : output.subarray(0, written)
}

const DECOMPRESS_HANDLERS: DecompressHandlers = {
  lz4: lz4Decompress,
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

export interface PrefixScanProgress {
  offset: number
  size: number
  chunks: number
  bytesRead: number
}

export interface McapOpenOptions {
  metadataOnly?: boolean
  indexUrl?: string
  signal?: AbortSignal
  onProgress?: (progress: PrefixScanProgress) => void
}

interface ServerChunkIndex {
  start_time: string
  end_time: string
  offset: number
  length: number
  compression: string
  compressed_size: number
  uncompressed_size: number
  channel_ids: number[]
  message_index_length: number
}

interface ServerRecordingIndex {
  size: number
  offset: number
  closed: boolean
  chunks: ServerChunkIndex[]
  message_counts: Record<string, string>
  records: string
}

interface PrefixScanState {
  offset: number
  closed: boolean
  schemas: Map<number, McapSchema>
  channels: Map<number, McapChannel>
  chunkIndexes: McapChunkIndex[]
  messageCountByChannel: Map<number, bigint>
  openedChunkOffsets: Set<number>
  indexUrl: string
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

function parseRecords(data: Uint8Array): { records: TypedMcapRecord[], consumed: number } {
  const stream = new McapStreamReader({ noMagicPrefix: true, validateCrcs: false })
  stream.append(data)
  const records: TypedMcapRecord[] = []
  for (let record = stream.nextRecord(); record; record = stream.nextRecord()) {
    records.push(record)
  }
  return { records, consumed: data.byteLength - stream.bytesRemaining() }
}

function recordView(data: Uint8Array, offset = 0): DataView {
  return new DataView(data.buffer, data.byteOffset + offset, data.byteLength - offset)
}

function* iterateChunkRecords(data: Uint8Array): Generator<{
  opcode: number
  view: DataView
  offset: number
  total: number
}> {
  let offset = 0
  while (offset + 9 <= data.length) {
    const view = recordView(data, offset)
    const opcode = view.getUint8(0)
    const recordLength = Number(view.getBigUint64(1, true))
    const total = 9 + recordLength
    if (offset + total > data.length) {
      break
    }
    yield {
      opcode, view, offset, total,
    }
    offset += total
  }
}

function parseChunkRecord(record: Uint8Array): Extract<TypedMcapRecord, { type: 'Chunk' }> | null {
  const stream = new McapStreamReader({
    includeChunks: true,
    noMagicPrefix: true,
    validateCrcs: false,
  })
  stream.append(record)
  const chunk = stream.nextRecord()
  if (!chunk || chunk.type !== 'Chunk') {
    return null
  }
  return chunk
}

function decompressChunk(chunk: Extract<TypedMcapRecord, { type: 'Chunk' }>): Uint8Array {
  if (chunk.compression === '') {
    return chunk.records
  }
  const decompress = DECOMPRESS_HANDLERS[chunk.compression]
  if (!decompress) {
    throw new Error(`Unsupported MCAP chunk compression: '${chunk.compression}'.`)
  }
  return decompress(chunk.records, chunk.uncompressedSize)
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

function decodeBase64(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes
}

function chunkFromServer(entry: ServerChunkIndex): McapChunkIndex {
  return {
    startTime: BigInt(entry.start_time),
    endTime: BigInt(entry.end_time),
    offset: entry.offset,
    length: entry.length,
    compression: entry.compression,
    compressedSize: entry.compressed_size,
    uncompressedSize: entry.uncompressed_size,
    channelIds: [...entry.channel_ids],
    messageIndexLength: entry.message_index_length,
  }
}

function parseServerRecordingIndex(payload: unknown): ServerRecordingIndex {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Invalid server index payload.')
  }
  const page = payload as Partial<ServerRecordingIndex>
  if (
    typeof page.size !== 'number'
    || typeof page.offset !== 'number'
    || typeof page.closed !== 'boolean'
    || !Array.isArray(page.chunks)
    || !page.message_counts
    || typeof page.message_counts !== 'object'
    || typeof page.records !== 'string'
  ) {
    throw new Error('Invalid server index payload.')
  }
  for (const entry of page.chunks) {
    if (
      !entry
      || typeof entry !== 'object'
      || typeof entry.start_time !== 'string'
      || typeof entry.end_time !== 'string'
      || typeof entry.offset !== 'number'
      || typeof entry.length !== 'number'
      || typeof entry.compression !== 'string'
      || typeof entry.compressed_size !== 'number'
      || typeof entry.uncompressed_size !== 'number'
      || !Array.isArray(entry.channel_ids)
      || typeof entry.message_index_length !== 'number'
    ) {
      throw new Error('Invalid server index chunk.')
    }
  }
  return page as ServerRecordingIndex
}

export class McapIndexedReader {
  private chunkIndexCursor: number | null

  private pendingLoad: Promise<boolean> = Promise.resolve(false)

  private chunkCache = new Map<number, Uint8Array>()

  private chunkCacheBytes = 0

  private chunkLoads = new Map<number, Promise<Uint8Array>>()

  private extendTask: Promise<boolean> | null = null

  private constructor(
    public readonly source: ByteSource,
    public readonly summary: McapSummary,
    private chunkIndexGroup: SummaryGroup | null,
    private prefixState: PrefixScanState | null = null,
  ) {
    this.chunkIndexCursor = chunkIndexGroup?.start ?? null
  }

  /**
   * Reads the index of a recording. Schemas, channels and statistics are fetched up front, which
   * costs a few tens of kilobytes whatever the recording size, while the chunk index is loaded in
   * windows as playback needs it. With `metadataOnly` the chunk index is never read, at the price of
   * not being able to read messages. An ongoing recording has no footer until it is closed; complete
   * chunks already on disk are indexed instead, so playback can watch what has been written so far.
   */
  static async open(source: ByteSource, options: McapOpenOptions = {}): Promise<McapIndexedReader> {
    const {
      metadataOnly = false, indexUrl, signal, onProgress,
    } = options
    const size = await source.size(signal)
    if (size < MAGIC_SIZE + 9) {
      throw new Error('File is too small to be an MCAP recording.')
    }

    if (size >= MAGIC_SIZE * 2 + FOOTER_RECORD_SIZE) {
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
      if (footer && footer.summaryStart !== 0n) {
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
        const reader = new McapIndexedReader(source, summary, metadataOnly ? null : chunkIndex)
        if (!metadataOnly) {
          await reader.loadMoreChunkIndexes(signal)
        }
        return reader
      }
    }

    if (!indexUrl) {
      throw new Error('This recording is still being written and no index was offered for it.')
    }
    const scanned = await McapIndexedReader.openFromServerIndex(source, indexUrl, signal, onProgress)
    return new McapIndexedReader(source, scanned.summary, null, scanned.state)
  }

  /**
   * Indexes complete chunks written since the last scan. Returns true when new chunks are available
   * to play. An ongoing recording is still open, so this is how playback learns about frames that
   * landed after the card was opened.
   */
  async extendWrittenPrefix(signal?: AbortSignal): Promise<boolean> {
    const state = this.prefixState
    if (!state || state.closed) {
      return false
    }
    if (this.extendTask) {
      return this.extendTask
    }
    this.extendTask = this.extendWrittenPrefixLocked(state, signal).finally(() => {
      this.extendTask = null
    })
    return this.extendTask
  }

  private async extendWrittenPrefixLocked(state: PrefixScanState, signal?: AbortSignal): Promise<boolean> {
    const chunksBefore = state.chunkIndexes.length
    const extended = await McapIndexedReader.extendFromServerIndex(this.source, state, state.indexUrl, signal)
    if (!extended.grew) {
      return false
    }
    const summary = McapIndexedReader.summaryFromPrefix(state, extended.size)
    this.summary.size = summary.size
    this.summary.startTime = summary.startTime
    this.summary.endTime = summary.endTime
    if (state.closed) {
      this.prefixState = null
    }
    return state.chunkIndexes.length > chunksBefore
  }

  /** Channels that have messages but no name yet, because opening the recording stayed within its budget. */
  get unnamedChannelCount(): number {
    const state = this.prefixState
    if (!state) {
      return 0
    }
    return [...state.messageCountByChannel.keys()].filter((channelId) => !state.channels.has(channelId)).length
  }

  /**
   * Names every channel left unnamed by opening, downloading one chunk per channel. Only worth calling
   * when the user asks for something that needs the whole topic list, such as exporting data.
   */
  async nameRemainingChannels(
    signal?: AbortSignal,
    onProgress?: (progress: PrefixScanProgress) => void,
  ): Promise<boolean> {
    const state = this.prefixState
    if (!state) {
      return false
    }
    const namedBefore = state.channels.size
    await McapIndexedReader.resolvePrefixChannels(this.source, this.summary.size, state, Infinity, signal, onProgress)
    return state.channels.size > namedBefore
  }

  private static applyPrefixRecords(state: PrefixScanState, records: TypedMcapRecord[]): void {
    for (const record of records) {
      switch (record.type) {
        case 'Schema':
          state.schemas.set(record.id, toSchema(record))
          break
        case 'Channel':
          state.channels.set(record.id, toChannel(record))
          break
        case 'MessageIndex': {
          const count = BigInt(record.records.length)
          const previous = state.messageCountByChannel.get(record.channelId) ?? 0n
          state.messageCountByChannel.set(record.channelId, previous + count)
          const chunk = state.chunkIndexes[state.chunkIndexes.length - 1]
          if (chunk && !chunk.channelIds.includes(record.channelId)) {
            chunk.channelIds.push(record.channelId)
          }
          break
        }
        default:
          break
      }
    }
  }

  private static async resolvePrefixChannels(
    source: ByteSource,
    size: number,
    state: PrefixScanState,
    budgetBytes: number,
    signal?: AbortSignal,
    onProgress?: (progress: PrefixScanProgress) => void,
  ): Promise<void> {
    const introducedBy = new Map<number, McapChunkIndex>()
    for (const chunk of state.chunkIndexes) {
      for (const channelId of chunk.channelIds) {
        if (!introducedBy.has(channelId)) {
          introducedBy.set(channelId, chunk)
        }
      }
    }

    let spent = 0
    while (true) {
      const chunk = [...state.messageCountByChannel.entries()]
        .filter(([channelId]) => !state.channels.has(channelId))
        .sort(([, left], [, right]) => Number(right - left))
        .map(([channelId]) => introducedBy.get(channelId))
        .find((candidate) => candidate !== undefined && !state.openedChunkOffsets.has(candidate.offset))
      if (!chunk || spent + chunk.length > budgetBytes) {
        break
      }
      spent += chunk.length
      state.openedChunkOffsets.add(chunk.offset)
      // eslint-disable-next-line no-await-in-loop
      McapIndexedReader.applyPrefixRecords(
        state,
        McapIndexedReader.recordsFromChunk(await source.read(chunk.offset, chunk.length, signal)),
      )
      onProgress?.({
        offset: state.offset, size, chunks: state.chunkIndexes.length, bytesRead: source.bytesRead,
      })
    }
  }

  private static async fetchServerIndexPage(
    indexUrl: string,
    from: number,
    signal?: AbortSignal,
  ): Promise<ServerRecordingIndex> {
    const pageUrl = new URL(indexUrl, window.location.origin)
    pageUrl.searchParams.set('from', String(from))
    pageUrl.searchParams.set('limit', String(SERVER_INDEX_PAGE_LIMIT))
    const response = await fetch(pageUrl.toString(), { signal })
    if (!response.ok) {
      throw new Error(`Server index request failed (${response.status}).`)
    }
    return parseServerRecordingIndex(await response.json())
  }

  private static applyServerIndexPage(state: PrefixScanState, page: ServerRecordingIndex): void {
    state.offset = page.offset
    state.closed = page.closed
    for (const entry of page.chunks) {
      state.chunkIndexes.push(chunkFromServer(entry))
    }
    for (const [channelIdText, countText] of Object.entries(page.message_counts)) {
      const channelId = Number(channelIdText)
      const count = BigInt(countText)
      const previous = state.messageCountByChannel.get(channelId) ?? 0n
      state.messageCountByChannel.set(channelId, previous + count)
    }
    if (page.records.length > 0) {
      McapIndexedReader.applyPrefixRecords(state, parseRecords(decodeBase64(page.records)).records)
    }
  }

  private static async loadServerIndexPages(
    source: ByteSource,
    state: PrefixScanState,
    indexUrl: string,
    from: number,
    signal?: AbortSignal,
    onProgress?: (progress: PrefixScanProgress) => void,
  ): Promise<number> {
    let requestFrom = from
    let previousOffset = -1
    let size = 0
    const shouldReport = createProgressGate()
    function reportProgress(force = false): void {
      if (!onProgress || !shouldReport(force)) {
        return
      }
      onProgress({
        offset: state.offset, size, chunks: state.chunkIndexes.length, bytesRead: source.bytesRead,
      })
    }
    while (true) {
      // eslint-disable-next-line no-await-in-loop
      const page = await McapIndexedReader.fetchServerIndexPage(indexUrl, requestFrom, signal)
      size = page.size
      McapIndexedReader.applyServerIndexPage(state, page)
      reportProgress()
      if (page.closed || page.offset === requestFrom || page.offset === previousOffset) {
        break
      }
      previousOffset = page.offset
      requestFrom = page.offset
    }

    reportProgress(true)
    return size
  }

  private static async openFromServerIndex(
    source: ByteSource,
    indexUrl: string,
    signal?: AbortSignal,
    onProgress?: (progress: PrefixScanProgress) => void,
  ): Promise<{ summary: McapSummary, state: PrefixScanState }> {
    const state: PrefixScanState = {
      offset: MAGIC_SIZE,
      closed: false,
      schemas: new Map(),
      channels: new Map(),
      chunkIndexes: [],
      messageCountByChannel: new Map(),
      openedChunkOffsets: new Set(),
      indexUrl,
    }
    onProgress?.({
      offset: state.offset, size: 0, chunks: 0, bytesRead: source.bytesRead,
    })
    const size = await McapIndexedReader.loadServerIndexPages(source, state, indexUrl, 0, signal, onProgress)
    if (state.chunkIndexes.length === 0) {
      throw new Error('Nothing has been written yet that can be played.')
    }
    await McapIndexedReader.resolvePrefixChannels(source, size, state, CHANNEL_NAMING_BUDGET_BYTES, signal, onProgress)
    return { summary: McapIndexedReader.summaryFromPrefix(state, size), state }
  }

  private static async extendFromServerIndex(
    source: ByteSource,
    state: PrefixScanState,
    indexUrl: string,
    signal?: AbortSignal,
  ): Promise<{ grew: boolean, size: number }> {
    const chunksBefore = state.chunkIndexes.length
    const size = await McapIndexedReader.loadServerIndexPages(source, state, indexUrl, state.offset, signal)
    return { grew: state.chunkIndexes.length > chunksBefore, size }
  }

  private static summaryFromPrefix(state: PrefixScanState, size: number): McapSummary {
    state.chunkIndexes.sort((left, right) => Number(left.startTime - right.startTime))
    return {
      size,
      startTime: state.chunkIndexes[0].startTime,
      endTime: state.chunkIndexes[state.chunkIndexes.length - 1].endTime,
      schemas: state.schemas,
      channels: state.channels,
      chunkIndexes: state.chunkIndexes,
      messageCountByChannel: state.messageCountByChannel,
    }
  }

  private static recordsFromChunk(record: Uint8Array): TypedMcapRecord[] {
    const chunk = parseChunkRecord(record)
    if (!chunk) {
      return []
    }
    let data: Uint8Array
    try {
      data = decompressChunk(chunk)
    } catch {
      return []
    }

    const records: TypedMcapRecord[] = []
    for (const {
      opcode, offset, total,
    } of iterateChunkRecords(data)) {
      if (opcode === Opcode.SCHEMA || opcode === Opcode.CHANNEL) {
        try {
          records.push(...parseRecords(data.subarray(offset, offset + total)).records)
        } catch {
          break
        }
      }
    }
    return records
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

  async loadRemainingChunkIndexes(signal?: AbortSignal, onWindow?: () => void): Promise<void> {
    while (!this.chunkIndexComplete) {
      // eslint-disable-next-line no-await-in-loop
      if (!await this.loadMoreChunkIndexes(signal)) {
        return
      }
      onWindow?.()
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
    // Walk opcodes instead of McapStreamReader: a chunk holds every channel in its time span, and
    // the reader throws if it sees a message whose Channel record was never loaded.
    const data = await this.readChunkData(chunkIndex, signal)
    const messages: McapMessage[] = []
    for (const {
      opcode, view, offset, total,
    } of iterateChunkRecords(data)) {
      const recordLength = total - 9
      if (opcode === Opcode.MESSAGE && recordLength >= 22 && view.getUint16(9, true) === channelId) {
        messages.push({
          channelId,
          sequence: view.getUint32(11, true),
          logTime: view.getBigUint64(15, true),
          data: data.subarray(offset + MESSAGE_HEADER_SIZE, offset + total),
        })
      }
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
    return whileWaiting(load, signal, 'The read was aborted.')
  }

  private async downloadChunk(chunkIndex: number): Promise<Uint8Array> {
    const index = this.summary.chunkIndexes[chunkIndex]
    if (!index) {
      throw new Error(`Chunk ${chunkIndex} is out of range.`)
    }

    const record = await this.source.read(index.offset, index.length)
    const chunk = parseChunkRecord(record)
    if (!chunk) {
      throw new Error(`Expected a chunk record at offset ${index.offset}.`)
    }
    return decompressChunk(chunk)
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
