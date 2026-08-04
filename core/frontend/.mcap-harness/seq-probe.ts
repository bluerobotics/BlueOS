import { openSync, readSync, statSync } from 'fs'

import VideoFrameStream from '../src/libs/mcap/frame-stream'
import { McapIndexedReader } from '../src/libs/mcap/reader'
import { ByteSource } from '../src/libs/mcap/source'
import { listVideoTracks, VideoTrack } from '../src/libs/mcap/video-track'

class FileSource implements ByteSource {
  bytesRead = 0

  private fd: number

  constructor(private path: string) {
    this.fd = openSync(path, 'r')
  }

  async size(): Promise<number> {
    return statSync(this.path).size
  }

  async read(offset: number, length: number): Promise<Uint8Array> {
    const buffer = Buffer.allocUnsafe(length)
    const read = readSync(this.fd, buffer, 0, length, offset)
    this.bytesRead += read
    return new Uint8Array(buffer.buffer, buffer.byteOffset, read)
  }
}

/**
 * Reads a track with every `drop`th message taken away, which is what a recording written by a
 * recorder that lost frames looks like, and checks the loss the stream reports against the truth.
 */
async function checkLossAccounting(
  reader: McapIndexedReader,
  track: VideoTrack,
  drop: number,
  frames: number,
): Promise<void> {
  let seen = 0
  const droppedSequences: number[] = []
  const original = reader.readChunkMessages.bind(reader)
  // eslint-disable-next-line no-param-reassign
  reader.readChunkMessages = async (chunkIndex, channelId, signal) => {
    const messages = await original(chunkIndex, channelId, signal)
    return messages.filter((message) => {
      seen += 1
      if (seen % drop !== 0) {
        return true
      }
      droppedSequences.push(message.sequence)
      return false
    })
  }

  const stream = new VideoFrameStream(reader, track)
  stream.seekToStart()
  let first: number | null = null
  let last = 0
  for (let index = 0; index < frames; index += 1) {
    // eslint-disable-next-line no-await-in-loop
    const frame = await stream.next()
    if (!frame) {
      break
    }
    first = first ?? frame.sequence
    last = frame.sequence
  }
  const { framesRead, framesLost } = stream.stats
  // Only the frames missing between the first and last frame actually read can be noticed; whole
  // chunks are filtered here, so the ones past the end of the read are not part of the comparison.
  const expected = droppedSequences.filter((sequence) => sequence > (first ?? 0) && sequence < last).length
  const verdict = framesLost === expected ? 'ok' : `MISMATCH, expected ${expected}`
  console.log(`  loss accounting with every ${drop}th message dropped: read ${framesRead} frames `
    + `(sequence ${first} to ${last}), reported lost ${framesLost}, actually missing ${expected} -> ${verdict}`)
  // eslint-disable-next-line no-param-reassign
  reader.readChunkMessages = original
}

async function main(): Promise<void> {
  const [path, chunkArgument] = process.argv.slice(2)
  const chunks = Number(chunkArgument ?? 3)
  const reader = await McapIndexedReader.open(new FileSource(path))
  for (const track of listVideoTracks(reader)) {
    // eslint-disable-next-line no-await-in-loop
    while (reader.chunkIndexesForChannel(track.channelId).length < chunks && await reader.loadMoreChunkIndexes()) {
      // The chunk index is read in windows, so it has to be pulled in before chunks can be read.
    }
    const positions = reader.chunkIndexesForChannel(track.channelId).slice(0, chunks)
    const sequences: number[] = []
    for (const position of positions) {
      // eslint-disable-next-line no-await-in-loop
      const messages = await reader.readChunkMessages(position, track.channelId)
      sequences.push(...messages.map((message) => message.sequence))
    }
    let gaps = 0
    let missing = 0
    let nonMonotonic = 0
    for (let index = 1; index < sequences.length; index += 1) {
      const delta = sequences[index] - sequences[index - 1]
      if (delta > 1) {
        gaps += 1
        missing += delta - 1
      } else if (delta <= 0) {
        nonMonotonic += 1
      }
    }
    console.log(`${track.name}: ${sequences.length} messages, first ${sequences[0]}, last `
      + `${sequences[sequences.length - 1]}, gaps ${gaps} (${missing} missing), non-monotonic ${nonMonotonic}`)
    console.log(`  head: ${sequences.slice(0, 12).join(' ')}`)

    const drop = Number(process.env.DROP ?? 0)
    if (drop > 1) {
      // eslint-disable-next-line no-await-in-loop
      await checkLossAccounting(reader, track, drop, sequences.length)
    }
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
