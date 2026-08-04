import {
  closeSync, openSync, readSync, statSync, writeFileSync,
} from 'fs'

import { CodecConfig, ParameterSetCache, toMp4Sample } from '../src/libs/mcap/codec'
import VideoFrameStream from '../src/libs/mcap/frame-stream'
import { buildFragment, buildInitSegment, Mp4Sample } from '../src/libs/mcap/mp4'
import { McapIndexedReader } from '../src/libs/mcap/reader'
import { ByteSource } from '../src/libs/mcap/source'
import { listVideoTracks } from '../src/libs/mcap/video-track'

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

  close(): void {
    closeSync(this.fd)
  }
}

async function main(): Promise<void> {
  const [path, output, secondsArgument, seekArgument] = process.argv.slice(2)
  const wantedSeconds = Number(secondsArgument ?? 10)
  const seekSeconds = seekArgument === undefined ? null : Number(seekArgument)

  const source = new FileSource(path)
  const metadataReader = await McapIndexedReader.open(source, { metadataOnly: true })
  console.log(`  metadata-only index cost: ${(source.bytesRead / 1024).toFixed(1)} kB`
    + `, duration ${(Number(metadataReader.summary.endTime - metadataReader.summary.startTime) / 1e9).toFixed(2)} s`
    + `, video tracks ${listVideoTracks(metadataReader).map((item) => item.name).join(', ') || 'none'}`)
  source.bytesRead = 0
  const reader = await McapIndexedReader.open(source)
  const { summary } = reader
  const durationSeconds = Number(summary.endTime - summary.startTime) / 1e9
  console.log(`file: ${path}`)
  console.log(`  size: ${(summary.size / 1e6).toFixed(1)} MB, duration: ${durationSeconds.toFixed(2)} s`
    + `, chunks: ${summary.chunkIndexes.length}, channels: ${summary.channels.size}`)
  console.log(`  index cost: ${(source.bytesRead / 1024).toFixed(1)} kB`)

  const tracks = listVideoTracks(reader)
  if (tracks.length === 0) {
    console.log('  no video tracks')
    return
  }
  for (const track of tracks) {
    console.log(`  track: ${track.name} (channel ${track.channelId}, ${track.frameCount} frames)`)
  }

  const wanted = process.env.TRACK
  const track = wanted === undefined
    ? tracks.reduce((best, item) => (item.frameCount > best.frameCount ? item : best))
    : tracks.find((item) => item.name === wanted)
  if (!track) {
    throw new Error(`no track named ${wanted}`)
  }
  console.log(`  playing: ${track.name}`)
  const stream = new VideoFrameStream(reader, track)

  const beforeSeek = source.bytesRead
  if (seekSeconds === null) {
    stream.seekToStart()
  } else {
    await stream.seekToKeyframe(seekSeconds)
  }
  console.log(`  keyframe lookup cost: ${((source.bytesRead - beforeSeek) / 1024).toFixed(1)} kB`)

  const parts: Uint8Array[] = []
  let config: CodecConfig | null = null
  let frames: { logTime: bigint, data: Uint8Array, isKeyframe: boolean }[] = []
  let firstTime: bigint | null = null
  let lastTime: bigint | null = null
  let sequence = 1
  let keyframes = 0
  let droppedBeforeKeyframe = 0
  let sampleCount = 0
  const parameterSets = new ParameterSetCache()

  const flush = (all: boolean): void => {
    const batch = all ? frames : frames.slice(0, -1)
    if (batch.length === 0) {
      return
    }
    frames = all ? [] : frames.slice(-1)
    const rest = frames
    const samples: Mp4Sample[] = batch.map((frame, index) => {
      const next = batch[index + 1] ?? rest[0]
      const duration = next ? Math.round(Number(next.logTime - frame.logTime) / 1000) : 33_333
      return {
        data: frame.data,
        duration: Math.min(Math.max(duration, 1000), 10_000_000),
        isKeyframe: frame.isKeyframe,
      }
    })
    sampleCount += samples.length
    const base = Math.round(Number(batch[0].logTime - summary.startTime) / 1000)
    parts.push(buildFragment(samples, base, sequence))
    sequence += 1
  }

  const startBytes = source.bytesRead
  for (;;) {
    // eslint-disable-next-line no-await-in-loop
    const frame = await stream.next()
    if (!frame) {
      break
    }
    const sample = toMp4Sample(frame.data, frame.format, parameterSets)
    if (!config) {
      if (!sample.isKeyframe) {
        droppedBeforeKeyframe += 1
        if (droppedBeforeKeyframe % 30 === 0) {
          // eslint-disable-next-line no-await-in-loop
          await stream.skipToKeyframeHint()
        }
        continue
      }
      config = parameterSets.buildConfig(frame.format)
      if (!config) {
        throw new Error('keyframe without parameter sets')
      }
      console.log(`  codec: ${config.codec} ${config.width}x${config.height}`
        + ` (${config.description.length} byte description), format: ${frame.format}`)
      parts.push(buildInitSegment(config))
      firstTime = frame.logTime
    }
    if (sample.isKeyframe) {
      keyframes += 1
    }
    lastTime = frame.logTime
    frames.push({ logTime: frame.logTime, data: sample.data, isKeyframe: sample.isKeyframe })
    if (frames.length > 1 && Number(frames[frames.length - 1].logTime - frames[0].logTime) / 1e9 >= 0.5) {
      flush(false)
    }
    if (firstTime !== null && Number(frame.logTime - firstTime) / 1e9 >= wantedSeconds) {
      break
    }
  }
  flush(true)

  const mediaSeconds = firstTime !== null && lastTime !== null ? Number(lastTime - firstTime) / 1e9 : 0
  const payload = source.bytesRead - startBytes
  const startOffset = firstTime === null ? 0 : Number(firstTime - summary.startTime) / 1e9
  console.log(`  frames dropped before first keyframe: ${droppedBeforeKeyframe}, keyframes: ${keyframes}`)
  console.log(`  muxed ${sampleCount} samples covering ${mediaSeconds.toFixed(2)} s`
    + ` starting at ${startOffset.toFixed(2)} s`)
  console.log(`  downloaded ${(payload / 1e6).toFixed(2)} MB for playback`
    + ` (${((payload * 8) / 1e6 / Math.max(mediaSeconds, 0.001)).toFixed(1)} Mbps)`)
  console.log(`  total read: ${(source.bytesRead / 1e6).toFixed(2)} MB of ${(summary.size / 1e6).toFixed(1)} MB`)

  const total = parts.reduce((size, part) => size + part.length, 0)
  const file = new Uint8Array(total)
  let offset = 0
  for (const part of parts) {
    file.set(part, offset)
    offset += part.length
  }
  writeFileSync(output, file)
  console.log(`  wrote ${output} (${(total / 1e6).toFixed(2)} MB)`)
  source.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
