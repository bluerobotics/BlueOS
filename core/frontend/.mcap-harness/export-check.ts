/** Saves a recording's video stream as MP4 the same way the browser does, for checking with ffmpeg. */
import { writeFileSync } from 'fs'

import { listMcapChannels } from '../src/libs/mcap/channels'
import { exportTrackAsMp4 } from '../src/libs/mcap/export'
import { openMcapVideoRecording } from '../src/libs/mcap/player'
import { McapIndexedReader } from '../src/libs/mcap/reader'
import { listVideoTracks } from '../src/libs/mcap/video-track'
import FileSource from './file-source'

/** Part of the recording to save, as the player would mark it: FROM=90 TO=120 saves those seconds. */
function wantedRange(): { startSeconds: number, endSeconds: number } | undefined {
  const { FROM, TO } = process.env
  if (!FROM && !TO) {
    return undefined
  }
  return { startSeconds: Number(FROM ?? 0), endSeconds: TO ? Number(TO) : Infinity }
}

/** Exports every wanted track. With TRACK=all they run together, sharing one reader. */
async function run(path: string, output: string): Promise<void> {
  const source = new FileSource(path)
  const reader = await McapIndexedReader.open(source)
  const tracks = listVideoTracks(reader)
  const wanted = process.env.TRACK
  const chosen = !wanted || wanted === 'all' ? tracks : tracks.filter((item) => item.name === wanted)
  if (chosen.length === 0) {
    throw new Error(`No track ${wanted ?? ''} in ${path}: ${tracks.map((item) => item.name).join(', ')}`)
  }

  const recording = {
    reader,
    tracks,
    channels: listMcapChannels(reader),
    durationSeconds: Number(reader.summary.endTime - reader.summary.startTime) / 1e9,
    startTime: reader.summary.startTime,
  } as Awaited<ReturnType<typeof openMcapVideoRecording>>

  const range = wantedRange()
  await Promise.all(chosen.map(async (track) => {
    let reported = 0
    const blob = await exportTrackAsMp4(recording, track, {
      range,
      onProgress: (progress) => {
        if (progress.seconds - reported >= 30) {
          reported = progress.seconds
          console.log(`  ${track.name}: ${progress.seconds.toFixed(1)}s of`
            + ` ${progress.durationSeconds.toFixed(1)}s, ${(progress.bytes / 1e6).toFixed(1)} MB`)
        }
      },
    })
    const file = chosen.length > 1 ? output.replace(/\.mp4$/, `-${track.name}.mp4`) : output
    writeFileSync(file, Buffer.from(await blob.arrayBuffer()))
    console.log(`${track.name}: wrote ${file}, ${(blob.size / 1e6).toFixed(2)} MB`)
  }))
  console.log(`read ${(source.bytesRead / 1e6).toFixed(2)} MB for ${chosen.length} stream(s)`)
}

const [path, output] = process.argv.slice(2)
run(path, output).catch((error) => {
  console.error(error)
  process.exit(1)
})
