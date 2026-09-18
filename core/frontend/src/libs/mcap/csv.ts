/**
 * Exports selected MCAP channels as one interleaved CSV file in the browser.
 */
import { parse as parseMessageDefinition } from '@foxglove/rosmsg'
import { MessageReader } from '@foxglove/rosmsg2-serialization'

import { throwIfAborted } from './abort'
import type { Mp4ExportRange } from './export'
import { createProgressGate } from './progress'
import {
  McapChannel, McapIndexedReader, McapMessage,
} from './reader'

const BASE_COLUMNS = ['log_time', 'topic', 'sequence'] as const

export interface CsvExportProgress {
  seconds: number
  durationSeconds: number
  bytes: number
  messages: number
}

export interface CsvExportOptions {
  range?: Mp4ExportRange
  onProgress?: (progress: CsvExportProgress) => void
  signal?: AbortSignal
}

export interface McapCsvRecording {
  reader: McapIndexedReader
  startTime: bigint
  durationSeconds: number
}

interface DecodedRow {
  logTime: bigint
  topic: string
  sequence: number
  fields: Record<string, string>
}

interface ChannelCursor {
  channelId: number
  topic: string
  positions: number[]
  positionIndex: number
  messages: McapMessage[]
  messageIndex: number
}

function toSeconds(startTime: bigint, logTime: bigint): number {
  return Number(logTime - startTime) / 1e9
}

function csvEscape(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }
  if (typeof value === 'number' || typeof value === 'bigint') {
    return String(value)
  }
  if (typeof value === 'string') {
    return value
  }
  return JSON.stringify(value)
}

function flattenValue(value: unknown, prefix: string, fields: Record<string, string>): void {
  if (value === null || value === undefined) {
    return
  }
  if (value instanceof Uint8Array) {
    const key = prefix === 'data' || prefix.endsWith('.data') ? prefix.replace(/\.?data$/, '.data_bytes') : `${prefix}_bytes`
    fields[key] = String(value.length)
    return
  }
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      flattenValue(value[index], `${prefix}.${index}`, fields)
    }
    return
  }
  if (typeof value === 'object') {
    for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
      const path = prefix ? `${prefix}.${key}` : key
      if (nested instanceof Uint8Array) {
        const bytesKey = key === 'data' ? prefix ? `${prefix}.data_bytes` : 'data_bytes' : `${path}_bytes`
        fields[bytesKey] = String(nested.length)
      } else if (nested !== null && typeof nested === 'object' && !Array.isArray(nested)) {
        flattenValue(nested, path, fields)
      } else {
        fields[path] = formatCell(nested)
      }
    }
    return
  }
  fields[prefix] = formatCell(value)
}

class ChannelDecoder {
  private readonly topic: string

  private readonly opaque: boolean

  private messageReader: MessageReader | null = null

  constructor(private readonly reader: McapIndexedReader, private readonly channel: McapChannel) {
    this.topic = channel.topic
    this.opaque = channel.messageEncoding === 'octet-stream'
    if (!this.opaque && channel.messageEncoding === 'cdr') {
      const schema = reader.summary.schemas.get(channel.schemaId)
      if (!schema) {
        throw new Error(`Recording is missing the schema for ${channel.topic}.`)
      }
      const text = new TextDecoder().decode(schema.data)
      this.messageReader = new MessageReader(parseMessageDefinition(text, { ros2: true }))
    }
  }

  decode(message: McapMessage): DecodedRow {
    if (this.opaque) {
      return {
        logTime: message.logTime,
        topic: this.topic,
        sequence: message.sequence,
        fields: { data_bytes: String(message.data.length) },
      }
    }
    const fields: Record<string, string> = {}
    if (this.channel.messageEncoding === 'json') {
      const parsed = JSON.parse(new TextDecoder().decode(message.data)) as unknown
      flattenValue(parsed, '', fields)
    } else if (this.messageReader) {
      flattenValue(this.messageReader.readMessage(message.data), '', fields)
    } else {
      throw new Error(`Unsupported message encoding '${this.channel.messageEncoding}' on ${this.topic}.`)
    }
    return {
      logTime: message.logTime,
      topic: this.topic,
      sequence: message.sequence,
      fields,
    }
  }
}

async function loadCursorChunk(
  cursor: ChannelCursor,
  reader: McapIndexedReader,
  signal?: AbortSignal,
): Promise<boolean> {
  while (cursor.positionIndex < cursor.positions.length) {
    const chunkIndex = cursor.positions[cursor.positionIndex]
    cursor.positionIndex += 1
    // eslint-disable-next-line no-await-in-loop
    const messages = await reader.readChunkMessages(chunkIndex, cursor.channelId, signal)
    if (messages.length > 0) {
      cursor.messages = messages
      cursor.messageIndex = 0
      return true
    }
  }
  cursor.messages = []
  cursor.messageIndex = 0
  return false
}

async function primeCursor(
  cursor: ChannelCursor,
  reader: McapIndexedReader,
  startLogTime: bigint,
  signal?: AbortSignal,
): Promise<void> {
  while (cursor.messageIndex >= cursor.messages.length) {
    // eslint-disable-next-line no-await-in-loop
    if (!await loadCursorChunk(cursor, reader, signal)) {
      return
    }
  }
  while (cursor.messageIndex < cursor.messages.length && cursor.messages[cursor.messageIndex].logTime < startLogTime) {
    cursor.messageIndex += 1
    if (cursor.messageIndex >= cursor.messages.length) {
      // eslint-disable-next-line no-await-in-loop
      await loadCursorChunk(cursor, reader, signal)
    }
  }
}

async function advanceCursor(
  cursor: ChannelCursor,
  reader: McapIndexedReader,
  signal?: AbortSignal,
): Promise<void> {
  cursor.messageIndex += 1
  if (cursor.messageIndex >= cursor.messages.length) {
    await loadCursorChunk(cursor, reader, signal)
  }
}

function cursorHead(cursor: ChannelCursor): McapMessage | null {
  if (cursor.messageIndex >= cursor.messages.length) {
    return null
  }
  return cursor.messages[cursor.messageIndex]
}

async function buildCursors(
  reader: McapIndexedReader,
  channelIds: number[],
  startLogTime: bigint,
  signal?: AbortSignal,
): Promise<ChannelCursor[]> {
  await reader.loadChunkIndexesUntil(startLogTime, signal)
  const cursors: ChannelCursor[] = []
  for (const channelId of channelIds) {
    const channel = reader.summary.channels.get(channelId)
    if (!channel) {
      continue
    }
    const cursor: ChannelCursor = {
      channelId,
      topic: channel.topic,
      positions: reader.chunkIndexesForChannel(channelId),
      positionIndex: reader.findChunkIndexAtTime(channelId, startLogTime),
      messages: [],
      messageIndex: 0,
    }
    // eslint-disable-next-line no-await-in-loop
    await primeCursor(cursor, reader, startLogTime, signal)
    if (cursorHead(cursor)) {
      cursors.push(cursor)
    }
  }
  return cursors
}

async function collectRows(
  recording: McapCsvRecording,
  channelIds: number[],
  startLogTime: bigint,
  endLogTime: bigint | null,
  startSeconds: number,
  durationSeconds: number,
  onProgress?: (progress: CsvExportProgress) => void,
  signal?: AbortSignal,
): Promise<{ rows: DecodedRow[], fieldColumns: string[] }> {
  const { reader, startTime } = recording
  const decoders = new Map<number, ChannelDecoder>()
  for (const channelId of channelIds) {
    const channel = reader.summary.channels.get(channelId)
    if (channel) {
      decoders.set(channelId, new ChannelDecoder(reader, channel))
    }
  }

  const cursors = await buildCursors(reader, channelIds, startLogTime, signal)
  const rows: DecodedRow[] = []
  const fieldColumns = new Set<string>()
  let bytes = 0
  let messages = 0
  const shouldReport = createProgressGate()

  function report(logTime: bigint): void {
    if (!onProgress || !shouldReport()) {
      return
    }
    onProgress({
      seconds: Math.max(0, toSeconds(startTime, logTime) - startSeconds),
      durationSeconds,
      bytes,
      messages,
    })
  }

  for (;;) {
    throwIfAborted(signal, 'The export was cancelled.')
    let nextCursor: ChannelCursor | null = null
    let nextMessage: McapMessage | null = null
    for (const cursor of cursors) {
      const message = cursorHead(cursor)
      if (!message) {
        continue
      }
      if (!nextMessage || message.logTime < nextMessage.logTime) {
        nextCursor = cursor
        nextMessage = message
      }
    }
    if (!nextCursor || !nextMessage) {
      break
    }
    if (endLogTime !== null && nextMessage.logTime > endLogTime) {
      break
    }

    const decoder = decoders.get(nextCursor.channelId)
    if (decoder) {
      const row = decoder.decode(nextMessage)
      rows.push(row)
      for (const key of Object.keys(row.fields)) {
        fieldColumns.add(key)
      }
      messages += 1
      bytes += 64 + Object.values(row.fields).join(',').length
      report(nextMessage.logTime)
    }
    // eslint-disable-next-line no-await-in-loop
    await advanceCursor(nextCursor, reader, signal)
  }

  return { rows, fieldColumns: [...fieldColumns].sort() }
}

function rowLine(row: DecodedRow, columns: readonly string[], startTime: bigint): string {
  const cells = [
    String(toSeconds(startTime, row.logTime)),
    csvEscape(row.topic),
    String(row.sequence),
    ...columns.map((column) => csvEscape(row.fields[column] ?? '')),
  ]
  return `${cells.join(',')}\n`
}

/** Reads the selected channels over a clip range and returns one interleaved CSV file. */
export async function exportChannelsAsCsv(
  recording: McapCsvRecording,
  channelIds: number[],
  options: CsvExportOptions = {},
): Promise<Blob> {
  if (channelIds.length === 0) {
    throw new Error('Select at least one channel to export.')
  }

  const { onProgress, signal, range } = options
  const startSeconds = Math.max(0, range?.startSeconds ?? 0)
  const endSeconds = Math.min(range?.endSeconds ?? Infinity, recording.durationSeconds)
  const durationSeconds = Math.max(endSeconds - startSeconds, 0)
  const startLogTime = recording.startTime + BigInt(Math.round(startSeconds * 1e9))
  const endLogTime = range && Number.isFinite(range.endSeconds)
    ? recording.startTime + BigInt(Math.round(endSeconds * 1e9))
    : null

  const { rows, fieldColumns } = await collectRows(
    recording,
    channelIds,
    startLogTime,
    endLogTime,
    startSeconds,
    durationSeconds,
    onProgress,
    signal,
  )

  if (rows.length === 0) {
    throw new Error('The selected part of this recording holds no messages for the chosen channels.')
  }

  const columns = [...BASE_COLUMNS, ...fieldColumns]
  const parts: Blob[] = [new Blob([`${columns.join(',')}\n`])]
  let bytes = parts[0].size
  let messages = 0
  const shouldReport = createProgressGate()
  for (const row of rows) {
    throwIfAborted(signal, 'The export was cancelled.')
    const line = rowLine(row, fieldColumns, recording.startTime)
    parts.push(new Blob([line]))
    bytes += line.length
    messages += 1
    if (shouldReport()) {
      onProgress?.({
        seconds: durationSeconds,
        durationSeconds,
        bytes,
        messages,
      })
    }
  }

  return new Blob(parts, { type: 'text/csv' })
}
