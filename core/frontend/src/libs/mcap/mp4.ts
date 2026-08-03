/**
 * Minimal fragmented MP4 writer. Produces an initialization segment plus `moof`/`mdat` fragments,
 * which is exactly what Media Source Extensions consumes, and is also a valid MP4 file when the
 * pieces are concatenated.
 */
import { CodecConfig } from './codec'

export const MP4_TIMESCALE = 1_000_000

const TRACK_ID = 1
const KEYFRAME_FLAGS = 0x02000000
const DELTA_FRAME_FLAGS = 0x01010000

export interface Mp4Sample {
  data: Uint8Array
  /** Duration in `MP4_TIMESCALE` units. */
  duration: number
  isKeyframe: boolean
}

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((size, part) => size + part.length, 0)
  const output = new Uint8Array(total)
  let offset = 0
  for (const part of parts) {
    output.set(part, offset)
    offset += part.length
  }
  return output
}

function box(type: string, ...children: Uint8Array[]): Uint8Array {
  const payload = concat(children)
  const output = new Uint8Array(8 + payload.length)
  const view = new DataView(output.buffer)
  view.setUint32(0, output.length)
  for (let index = 0; index < 4; index += 1) {
    output[4 + index] = type.charCodeAt(index)
  }
  output.set(payload, 8)
  return output
}

class Writer {
  private bytes: number[] = []

  uint8(...values: number[]): Writer {
    this.bytes.push(...values.map((value) => value & 0xff))
    return this
  }

  uint16(value: number): Writer {
    return this.uint8(value >> 8, value)
  }

  uint32(value: number): Writer {
    return this.uint8(value >> 24, value >> 16, value >> 8, value)
  }

  uint64(value: number): Writer {
    const high = Math.floor(value / 2 ** 32)
    return this.uint32(high).uint32(value >>> 0)
  }

  ascii(value: string): Writer {
    return this.uint8(...[...value].map((character) => character.charCodeAt(0)))
  }

  zeros(count: number): Writer {
    return this.uint8(...new Array(count).fill(0))
  }

  raw(data: Uint8Array): Writer {
    this.bytes.push(...data)
    return this
  }

  build(): Uint8Array {
    return new Uint8Array(this.bytes)
  }
}

const UNITY_MATRIX = new Writer()
  .uint32(0x00010000).uint32(0).uint32(0)
  .uint32(0)
  .uint32(0x00010000)
  .uint32(0)
  .uint32(0)
  .uint32(0)
  .uint32(0x40000000)
  .build()

function sampleEntry(config: CodecConfig): Uint8Array {
  const configurationBox = config.sampleEntry === 'hvc1' ? 'hvcC' : 'avcC'
  const header = new Writer()
    .zeros(6)
    .uint16(1) // data_reference_index
    .zeros(16) // pre_defined + reserved
    .uint16(config.width)
    .uint16(config.height)
    .uint32(0x00480000) // 72 dpi horizontal
    .uint32(0x00480000) // 72 dpi vertical
    .uint32(0)
    .uint16(1) // frame_count
    .zeros(32) // compressor name
    .uint16(0x0018) // depth
    .uint16(0xffff) // pre_defined = -1
    .build()
  return box(config.sampleEntry, header, box(configurationBox, config.description))
}

export function buildInitSegment(config: CodecConfig): Uint8Array {
  const ftyp = box(
    'ftyp',
    new Writer().ascii('isom').uint32(0x200).ascii('isom')
      .ascii('iso2')
      .ascii('avc1')
      .ascii('mp41')
      .build(),
  )

  const mvhd = box('mvhd', new Writer()
    .uint32(0) // version + flags
    .uint32(0).uint32(0) // creation + modification time
    .uint32(MP4_TIMESCALE)
    .uint32(0) // duration, unknown for fragmented files
    .uint32(0x00010000) // rate
    .uint16(0x0100) // volume
    .zeros(10)
    .raw(UNITY_MATRIX)
    .zeros(24) // pre_defined
    .uint32(TRACK_ID + 1)
    .build())

  const tkhd = box('tkhd', new Writer()
    .uint32(0x00000007) // version 0, track enabled + in movie + in preview
    .uint32(0).uint32(0)
    .uint32(TRACK_ID)
    .uint32(0)
    .uint32(0) // duration
    .zeros(8)
    .uint16(0) // layer
    .uint16(0) // alternate_group
    .uint16(0) // volume
    .uint16(0)
    .raw(UNITY_MATRIX)
    .uint32(config.width * 0x10000)
    .uint32(config.height * 0x10000)
    .build())

  const mdhd = box('mdhd', new Writer()
    .uint32(0)
    .uint32(0).uint32(0)
    .uint32(MP4_TIMESCALE)
    .uint32(0)
    .uint16(0x55c4) // 'und' language
    .uint16(0)
    .build())

  const hdlr = box('hdlr', new Writer()
    .uint32(0)
    .uint32(0)
    .ascii('vide')
    .zeros(12)
    .ascii('VideoHandler')
    .zeros(1)
    .build())

  const stbl = box(
    'stbl',
    box('stsd', new Writer().uint32(0).uint32(1).build(), sampleEntry(config)),
    box('stts', new Writer().uint32(0).uint32(0).build()),
    box('stsc', new Writer().uint32(0).uint32(0).build()),
    box('stsz', new Writer().uint32(0).uint32(0).uint32(0)
      .build()),
    box('stco', new Writer().uint32(0).uint32(0).build()),
  )

  const minf = box(
    'minf',
    box('vmhd', new Writer().uint32(0x00000001).zeros(8).build()),
    box('dinf', box('dref', new Writer().uint32(0).uint32(1).build(), box('url ', new Writer().uint32(1).build()))),
    stbl,
  )

  const trak = box('trak', tkhd, box('mdia', mdhd, hdlr, minf))
  const mvex = box('mvex', box('trex', new Writer()
    .uint32(0)
    .uint32(TRACK_ID)
    .uint32(1) // default_sample_description_index
    .uint32(0)
    .uint32(0)
    .uint32(0)
    .build()))

  return concat([ftyp, box('moov', mvhd, trak, mvex)])
}

/**
 * Builds a media fragment. `baseMediaDecodeTime` places the samples on the media timeline, which is
 * what lets us append segments out of order after a seek.
 */
export function buildFragment(samples: Mp4Sample[], baseMediaDecodeTime: number, sequence: number): Uint8Array {
  function trun(dataOffset: number): Uint8Array {
    const writer = new Writer()
      .uint32(0x01000701) // version 1, data offset + per sample duration, size and flags
      .uint32(samples.length)
      .uint32(dataOffset)
    for (const sample of samples) {
      writer
        .uint32(sample.duration)
        .uint32(sample.data.length)
        .uint32(sample.isKeyframe ? KEYFRAME_FLAGS : DELTA_FRAME_FLAGS)
    }
    return box('trun', writer.build())
  }

  function moofFor(dataOffset: number): Uint8Array {
    return box(
      'moof',
      box('mfhd', new Writer().uint32(0).uint32(sequence).build()),
      box(
        'traf',
        box('tfhd', new Writer().uint32(0x00020000).uint32(TRACK_ID).build()), // default-base-is-moof
        box('tfdt', new Writer().uint32(0x01000000).uint64(baseMediaDecodeTime).build()),
        trun(dataOffset),
      ),
    )
  }

  const moof = moofFor(moofFor(0).length + 8)
  const mdat = box('mdat', concat(samples.map((sample) => sample.data)))
  return concat([moof, mdat])
}
