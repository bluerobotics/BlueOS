/** Reads every video stream of a recording at once, to measure what simultaneous playback costs. */
import VideoFrameStream from '../src/libs/mcap/frame-stream'
import { DecodableFrameCursor } from '../src/libs/mcap/frames'
import { McapIndexedReader } from '../src/libs/mcap/reader'
import { listVideoTracks } from '../src/libs/mcap/video-track'
import FileSource from './file-source'

class CountingFileSource extends FileSource {
  requests = 0

  async read(offset: number, length: number): Promise<Uint8Array> {
    this.requests += 1
    return super.read(offset, length)
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
  const source = new CountingFileSource(path)
  const reader = await McapIndexedReader.open(source)
  const tracks = listVideoTracks(reader)
  console.log(`${path.split('/').pop()}: ${tracks.length} stream(s): ${tracks.map((item) => item.name).join(', ')}`)
  if (tracks.length === 0) {
    return
  }

  const streams = tracks.map((track) => new VideoFrameStream(reader, track))
  const cursors = tracks.map((track, index) => new DecodableFrameCursor(streams[index], reader, track))
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
    const cursor = cursors[index]
    for (;;) {
      // eslint-disable-next-line no-await-in-loop
      const frame = await cursor.next()
      if (!frame) {
        break
      }
      const state = progress[index]
      if (state.codec === '') {
        const { decoderInfo } = cursor
        state.codec = decoderInfo ? `${decoderInfo.codec} ${decoderInfo.width}x${decoderInfo.height}` : ''
        firstTime[index] = frame.logTime
      }
      state.frames += 1
      state.keyframes = cursor.keyframes
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
