import { writeFileSync } from 'fs'

import VideoFrameStream from '../src/libs/mcap/frame-stream'
import { DecodableFrameCursor } from '../src/libs/mcap/frames'
import { AnnexBFrame, clampSampleDuration, muxFragmentedMp4 } from '../src/libs/mcap/mux'
import { McapIndexedReader } from '../src/libs/mcap/reader'
import { listVideoTracks } from '../src/libs/mcap/video-track'
import FileSource from './file-source'

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
  function busiest(left: typeof tracks[number], right: typeof tracks[number]): typeof tracks[number] {
    return right.frameCount > left.frameCount ? right : left
  }
  const track = wanted === undefined
    ? tracks.reduce(busiest)
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

  const parts: AnnexBFrame[] = []
  const cursor = new DecodableFrameCursor(stream, reader, track)
  let frames: { logTime: bigint, data: Uint8Array, isKeyframe: boolean }[] = []
  let firstTime: bigint | null = null
  let lastTime: bigint | null = null
  let sampleCount = 0

  function flush(all: boolean): void {
    const batch = all ? frames : frames.slice(0, -1)
    if (batch.length === 0) {
      return
    }
    frames = all ? [] : frames.slice(-1)
    const rest = frames
    for (let index = 0; index < batch.length; index += 1) {
      const frame = batch[index]
      const next = batch[index + 1] ?? rest[0]
      const duration = next
        ? clampSampleDuration(Number(next.logTime - frame.logTime) / 1e9)
        : 1 / 30
      parts.push({
        data: frame.data,
        timestamp: Number(frame.logTime - summary.startTime) / 1e9,
        duration,
        isKeyframe: frame.isKeyframe,
      })
      sampleCount += 1
    }
  }

  const startBytes = source.bytesRead
  for (;;) {
    // eslint-disable-next-line no-await-in-loop
    const frame = await cursor.next()
    if (!frame) {
      break
    }
    if (firstTime === null) {
      const { decoderInfo } = cursor
      if (decoderInfo) {
        console.log(`  codec: ${decoderInfo.codec} ${decoderInfo.width}x${decoderInfo.height}`
          + `, format: ${frame.format}`)
      }
      firstTime = frame.logTime
    }
    lastTime = frame.logTime
    frames.push({ logTime: frame.logTime, data: frame.annexB, isKeyframe: frame.isKeyframe })
    if (frames.length > 1 && Number(frames[frames.length - 1].logTime - frames[0].logTime) / 1e9 >= 0.5) {
      flush(false)
    }
    if (firstTime !== null && Number(frame.logTime - firstTime) / 1e9 >= wantedSeconds) {
      break
    }
  }
  flush(true)
  if (!cursor.decoderInfo) {
    throw new Error('keyframe without parameter sets')
  }
  const file = await muxFragmentedMp4(parts, cursor.decoderInfo)

  const mediaSeconds = firstTime !== null && lastTime !== null ? Number(lastTime - firstTime) / 1e9 : 0
  const payload = source.bytesRead - startBytes
  const startOffset = firstTime === null ? 0 : Number(firstTime - summary.startTime) / 1e9
  console.log(`  frames dropped before first keyframe: ${cursor.framesSkipped}, keyframes: ${cursor.keyframes}`)
  console.log(`  muxed ${sampleCount} samples covering ${mediaSeconds.toFixed(2)} s`
    + ` starting at ${startOffset.toFixed(2)} s`)
  console.log(`  downloaded ${(payload / 1e6).toFixed(2)} MB for playback`
    + ` (${(payload * 8 / 1e6 / Math.max(mediaSeconds, 0.001)).toFixed(1)} Mbps)`)
  console.log(`  total read: ${(source.bytesRead / 1e6).toFixed(2)} MB of ${(summary.size / 1e6).toFixed(1)} MB`)
  writeFileSync(output, file)
  console.log(`  wrote ${output} (${(file.byteLength / 1e6).toFixed(2)} MB)`)
  source.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
