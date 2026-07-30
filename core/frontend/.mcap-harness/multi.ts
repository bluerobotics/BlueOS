/** Reads every video stream of a recording at once, to measure what simultaneous playback costs. */
import { closeSync, openSync, readSync, statSync } from 'fs'

import { ParameterSetCache, toMp4Sample } from '../src/libs/mcap/codec'
import VideoFrameStream from '../src/libs/mcap/frame-stream'
import { McapIndexedReader } from '../src/libs/mcap/reader'
import { ByteSource } from '../src/libs/mcap/source'
import { listVideoTracks } from '../src/libs/mcap/video-track'

class FileSource implements ByteSource {
  bytesRead = 0

  requests = 0

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
    this.requests += 1
    return new Uint8Array(buffer.buffer, buffer.byteOffset, read)
  }

  close(): void {
    closeSync(this.fd)
  }
}

interface Progress {
  name: string
  frames: number
  keyframes: number
  seconds: number
  codec: string
  done: boolean
}

async function playAll(path: string, wantedSeconds: number, seekSeconds: number | null): Promise<void> {
  const source = new FileSource(path)
  const reader = await McapIndexedReader.open(source)
  const tracks = listVideoTracks(reader)
  console.log(`${path.split('/').pop()}: ${tracks.length} stream(s): ${tracks.map((item) => item.name).join(', ')}`)
  if (tracks.length === 0) {
    return
  }

  const streams = tracks.map((track) => new VideoFrameStream(reader, track))
  const parameterSets = tracks.map(() => new ParameterSetCache())
  const progress: Progress[] = tracks.map((track) => ({
    name: track.name, frames: 0, keyframes: 0, seconds: 0, codec: '', done: false,
  }))
  const firstTime: (bigint | null)[] = tracks.map(() => null)

  await Promise.all(streams.map(async (stream, index) => {
    if (seekSeconds === null) {
      stream.seekToStart()
    } else {
      await stream.seekToKeyframe(seekSeconds)
    }
    for (;;) {
      // eslint-disable-next-line no-await-in-loop
      const frame = await stream.next()
      if (!frame) {
        break
      }
      const sample = toMp4Sample(frame.data, frame.format, parameterSets[index])
      const state = progress[index]
      if (state.codec === '') {
        if (!sample.isKeyframe) {
          continue
        }
        const config = parameterSets[index].buildConfig(frame.format)
        if (!config) {
          state.codec = 'undecodable'
          break
        }
        state.codec = `${config.codec} ${config.width}x${config.height}`
        firstTime[index] = frame.logTime
      }
      state.frames += 1
      state.keyframes += sample.isKeyframe ? 1 : 0
      const start = firstTime[index]
      state.seconds = start === null ? 0 : Number(frame.logTime - start) / 1e9
      if (state.seconds >= wantedSeconds) {
        break
      }
    }
    progress[index].done = true
  }))

  for (const state of progress) {
    console.log(`  ${state.name.padEnd(32)} ${state.codec.padEnd(26)}`
      + ` ${state.frames} frames (${state.keyframes} key) covering ${state.seconds.toFixed(2)} s`)
  }
  console.log(`  downloaded ${(source.bytesRead / 1e6).toFixed(2)} MB in ${source.requests} requests`
    + ` for ${tracks.length} stream(s)`)
  source.close()
}

const [path, secondsArgument, seekArgument] = process.argv.slice(2)
playAll(path, Number(secondsArgument ?? 5), seekArgument === undefined ? null : Number(seekArgument))
  .catch((error) => {
    console.error(error)
    process.exit(1)
  })
