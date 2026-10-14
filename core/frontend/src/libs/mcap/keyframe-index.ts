/**
 * Locates keyframes using only the MCAP message indexes.
 *
 * Compressed video frames carry their parameter sets on keyframes, which makes keyframes several
 * times larger than delta frames. Message indexes tell us the size of every message for a few
 * kilobytes per chunk, so a keyframe can be found without downloading any video payload. The result
 * is a hint: the caller still decodes the bitstream and keeps scanning forward if the guess was off.
 */
import { McapIndexedReader, McapMessageEntry } from './reader'

/**
 * How much bigger than the typical frame a message has to be to look like a keyframe. Kept low on
 * purpose: a missed keyframe makes a seek land later than asked, while a false one only costs the
 * delta frames decoded before the real keyframe shows up.
 */
const KEYFRAME_SIZE_RATIO = 1.8
const MINIMUM_SAMPLES_FOR_MEDIAN = 8

export interface KeyframeHint {
  /** Position within the channel's chunk list. */
  position: number
  logTime: bigint
}

export class KeyframeLocator {
  private entriesByChunk = new Map<number, McapMessageEntry[]>()

  private observedSizes: number[] = []

  private unavailable = false

  constructor(
    private reader: McapIndexedReader,
    private channelId: number,
    private chunkPositions: () => number[],
  ) {}

  private async entriesAt(position: number, signal?: AbortSignal): Promise<McapMessageEntry[] | null> {
    const positions = this.chunkPositions()
    if (this.unavailable || position < 0 || position >= positions.length) {
      return null
    }
    const chunkIndex = positions[position]
    const cached = this.entriesByChunk.get(chunkIndex)
    if (cached) {
      return cached
    }

    const entries = await this.reader.readChunkMessageEntries(chunkIndex, this.channelId, signal)
    if (!entries) {
      this.unavailable = true
      return null
    }
    this.entriesByChunk.set(chunkIndex, entries)
    this.observedSizes.push(...entries.map((entry) => entry.size))
    return entries
  }

  private threshold(): number | null {
    if (this.observedSizes.length < MINIMUM_SAMPLES_FOR_MEDIAN) {
      return null
    }
    const sorted = [...this.observedSizes].sort((left, right) => left - right)
    const median = sorted[Math.floor(sorted.length / 2)]
    return median > 0 ? median * KEYFRAME_SIZE_RATIO : null
  }

  /** First chunk at or after `position` that looks like it contains a keyframe. */
  async findForward(position: number, maxChunks: number, signal?: AbortSignal): Promise<KeyframeHint | null> {
    const candidates: { position: number, entry: McapMessageEntry }[] = []
    for (let offset = 0; offset < maxChunks; offset += 1) {
      const current = position + offset
      // eslint-disable-next-line no-await-in-loop
      const entries = await this.entriesAt(current, signal)
      if (!entries) {
        break
      }
      candidates.push(...entries.map((entry) => ({ position: current, entry })))
      const threshold = this.threshold()
      if (threshold === null) {
        continue
      }
      const match = candidates.find(({ entry }) => entry.size >= threshold)
      if (match) {
        return { position: match.position, logTime: match.entry.logTime }
      }
      candidates.length = 0
    }
    return null
  }

  /** Last keyframe at or before `logTime`, searching backwards from the chunk that holds it. */
  async findBefore(
    logTime: bigint,
    position: number,
    maxChunks: number,
    signal?: AbortSignal,
  ): Promise<KeyframeHint | null> {
    for (let offset = 0; offset < maxChunks; offset += 1) {
      const current = position - offset
      if (current < 0) {
        break
      }
      // eslint-disable-next-line no-await-in-loop
      const entries = await this.entriesAt(current, signal)
      if (!entries) {
        break
      }
      const threshold = this.threshold()
      if (threshold === null) {
        continue
      }
      const match = [...entries].reverse().find((entry) => entry.size >= threshold && entry.logTime <= logTime)
      if (match) {
        return { position: current, logTime: match.logTime }
      }
    }
    return null
  }
}
