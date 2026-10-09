/**
 * ISO-BMFF muxing via mediabunny. Annex B H.264/H.265 packets go in; fMP4 for MSE and ordinary
 * MP4 for saving come out. Mediabunny parses parameter sets and writes avcC/hvcC, which is why
 * this file does not.
 *
 * Decoder codec strings and coded size come from mediabunny's Annex B parsers. They are not on the
 * package export map; Vite and tsconfig map `mediabunny/codec-data` onto that module. The first
 * EncodedVideoPacketSource.add still needs those values, and a probe-mux round trip would write the
 * placeholder size into tkhd/stsd.
 */
/* eslint-disable max-classes-per-file */
import {
  AppendOnlyStreamTarget,
  BufferTarget,
  EncodedPacket,
  EncodedVideoPacketSource,
  Mp4OutputFormat,
  Output,
} from 'mediabunny'
import {
  extractAvcDecoderConfigurationRecord,
  extractHevcDecoderConfigurationRecord,
  HevcNalUnitType,
  parseAvcSps,
  parseHevcSps,
} from 'mediabunny/codec-data'

import { videoCodecId, VideoFormat } from './codec'

export const MINIMUM_SAMPLE_DURATION_SECONDS = 0.001
/** Frames spanning a recording gap keep the last picture on screen instead of leaving a hole. */
export const MAXIMUM_SAMPLE_DURATION_SECONDS = 10

export interface VideoDecoderInfo {
  codec: string
  width: number
  height: number
  format: VideoFormat
}

export interface AnnexBFrame {
  data: Uint8Array
  /** Presentation time in seconds from the start of the recording. */
  timestamp: number
  duration: number
  isKeyframe: boolean
}

export function clampSampleDuration(seconds: number): number {
  return Math.min(Math.max(seconds, MINIMUM_SAMPLE_DURATION_SECONDS), MAXIMUM_SAMPLE_DURATION_SECONDS)
}

function decoderMeta(info: VideoDecoderInfo): EncodedVideoChunkMetadata {
  return {
    decoderConfig: {
      codec: info.codec,
      codedWidth: info.width,
      codedHeight: info.height,
    },
  }
}

function packetOf(frame: AnnexBFrame): EncodedPacket {
  return new EncodedPacket(frame.data, frame.isKeyframe ? 'key' : 'delta', frame.timestamp, frame.duration)
}

function hexByte(value: number): string {
  return value.toString(16).padStart(2, '0')
}

/** RFC 6381 prints HEVC compatibility flags with bit 0 as the LSB of the hex string. */
function reverseBitsU32(value: number): number {
  let bits = value
  bits = bits >> 1 & 0x55555555 | (bits & 0x55555555) << 1
  bits = bits >> 2 & 0x33333333 | (bits & 0x33333333) << 2
  bits = bits >> 4 & 0x0f0f0f0f | (bits & 0x0f0f0f0f) << 4
  bits = bits >> 8 & 0x00ff00ff | (bits & 0x00ff00ff) << 8
  bits = bits >> 16 & 0x0000ffff | (bits & 0x0000ffff) << 16
  return bits >>> 0
}

function avcCodecString(profile: number, compatibility: number, level: number): string {
  return `avc1.${hexByte(profile)}${hexByte(compatibility)}${hexByte(level)}`
}

function hevcCodecString(
  profileSpace: number,
  profileIdc: number,
  compatibilityFlags: number,
  tierFlag: number,
  levelIdc: number,
  constraintFlags: Uint8Array,
): string {
  const space = ['', 'A', 'B', 'C'][profileSpace] ?? ''
  const compatibility = reverseBitsU32(compatibilityFlags).toString(16).toUpperCase()
  const tier = tierFlag === 0 ? 'L' : 'H'
  const flags = [...constraintFlags]
  while (flags.length > 0 && flags[flags.length - 1] === 0) {
    flags.pop()
  }
  let codec = `hev1.${space}${profileIdc}.${compatibility}.${tier}${levelIdc}`
  if (flags.length > 0) {
    codec += `.${flags.map((flag) => flag.toString(16).toUpperCase()).join('.')}`
  }
  return codec
}

function missingParameterSets(format: VideoFormat): Error {
  return new Error(`This ${format.toUpperCase()} stream was recorded without the parameter sets`
    + ' needed to decode it, so no player can show it.')
}

/**
 * Reads codec string and coded size from an Annex B keyframe's parameter sets.
 */
export function probeDecoderInfo(format: VideoFormat, keyframe: Uint8Array): VideoDecoderInfo {
  if (format === 'h264') {
    const record = extractAvcDecoderConfigurationRecord(keyframe)
    const sps = record?.sequenceParameterSets[0]
    const info = sps ? parseAvcSps(sps) : null
    if (!record || !info) {
      throw missingParameterSets(format)
    }
    return {
      codec: avcCodecString(record.avcProfileIndication, record.profileCompatibility, record.avcLevelIndication),
      width: info.displayWidth,
      height: info.displayHeight,
      format,
    }
  }

  const record = extractHevcDecoderConfigurationRecord(keyframe)
  const sps = record?.arrays.find((entry) => entry.nalUnitType === HevcNalUnitType.SPS_NUT)?.nalUnits[0]
  const info = sps ? parseHevcSps(sps) : null
  if (!record || !info) {
    throw missingParameterSets(format)
  }
  return {
    codec: hevcCodecString(
      record.generalProfileSpace,
      record.generalProfileIdc,
      record.generalProfileCompatibilityFlags,
      record.generalTierFlag,
      record.generalLevelIdc,
      record.generalConstraintIndicatorFlags,
    ),
    width: info.displayWidth,
    height: info.displayHeight,
    format,
  }
}

/** One fragmented MP4 file covering the given frames, for MSE when a whole segment is on hand. */
export async function muxFragmentedMp4(frames: AnnexBFrame[], info: VideoDecoderInfo): Promise<Uint8Array> {
  if (frames.length === 0) {
    throw new Error('No video frames to mux.')
  }
  const chunks: Uint8Array[] = []
  let bytes = 0
  const packets = new EncodedVideoPacketSource(videoCodecId(info.format))
  const output = new Output({
    format: new Mp4OutputFormat({
      fastStart: 'fragmented',
      minimumFragmentDuration: 0,
    }),
    target: new AppendOnlyStreamTarget(new WritableStream({
      write(data: Uint8Array) {
        const copy = data.slice()
        chunks.push(copy)
        bytes += copy.byteLength
      },
    })),
  })
  output.addVideoTrack(packets)
  await output.start()
  await packets.add(packetOf(frames[0]), decoderMeta(info))
  for (const frame of frames.slice(1)) {
    // eslint-disable-next-line no-await-in-loop
    await packets.add(packetOf(frame))
  }
  packets.close()
  await output.finalize()

  const merged = new Uint8Array(bytes)
  let offset = 0
  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.byteLength
  }
  return merged
}

/**
 * Incremental fMP4 writer for MSE. Bytes are append-only: initialization segment, then fragments.
 * Cancel and open a new stream after a seek; an in-flight output cannot jump its timeline.
 */
export class Mp4MediaStream {
  private packets: EncodedVideoPacketSource

  private output: Output

  private started = false

  private constructor(
    private info: VideoDecoderInfo,
    onData: (data: Uint8Array) => Promise<void> | void,
    fragmentSeconds: number,
  ) {
    this.packets = new EncodedVideoPacketSource(videoCodecId(info.format))
    this.output = new Output({
      format: new Mp4OutputFormat({
        fastStart: 'fragmented',
        minimumFragmentDuration: fragmentSeconds,
      }),
      target: new AppendOnlyStreamTarget(new WritableStream({
        write: (data: Uint8Array) => onData(data.slice()),
      })),
    })
    this.output.addVideoTrack(this.packets)
  }

  static async open(
    info: VideoDecoderInfo,
    onData: (data: Uint8Array) => Promise<void> | void,
    fragmentSeconds: number,
  ): Promise<Mp4MediaStream> {
    const stream = new Mp4MediaStream(info, onData, fragmentSeconds)
    await stream.output.start()
    return stream
  }

  async add(frame: AnnexBFrame): Promise<void> {
    if (!this.started) {
      this.started = true
      await this.packets.add(packetOf(frame), decoderMeta(this.info))
      return
    }
    await this.packets.add(packetOf(frame))
  }

  /**
   * Writes the current fragment now. Mediabunny otherwise waits for the next keyframe, which for a camera GOP is
   * about a second of freeze then a burst.
   */
  async flushFragment(): Promise<void> {
    const muxer = (this.output as Output & {
      _muxer: { forceFragmentFinalization: () => Promise<void> }
    })._muxer
    await muxer.forceFragmentFinalization()
  }

  async finalize(): Promise<void> {
    this.packets.close()
    if (this.output.state === 'started') {
      await this.output.finalize()
    }
  }

  async cancel(): Promise<void> {
    if (this.output.state === 'started' || this.output.state === 'pending') {
      await this.output.cancel()
    }
  }
}

/**
 * Incremental ordinary MP4 writer for saving a recording.
 *
 * Regular MP4 patches the mdat size after the media is written, so it cannot go through
 * AppendOnlyStreamTarget. BufferTarget is the matching in-memory sink for that seek.
 */
export class Mp4FileStream {
  private packets: EncodedVideoPacketSource

  private output: Output<BufferTarget>

  private target: BufferTarget

  private started = false

  private constructor(private info: VideoDecoderInfo, onBytes?: (bytes: number) => void) {
    this.packets = new EncodedVideoPacketSource(videoCodecId(info.format))
    this.target = new BufferTarget()
    this.output = new Output({
      format: new Mp4OutputFormat({ fastStart: false }),
      target: this.target,
    })
    this.output.addVideoTrack(this.packets)
    if (onBytes) {
      this.target.on('write', ({ end }) => {
        onBytes(end)
      })
    }
  }

  static async open(
    info: VideoDecoderInfo,
    onBytes?: (bytes: number) => void,
  ): Promise<Mp4FileStream> {
    const stream = new Mp4FileStream(info, onBytes)
    await stream.output.start()
    return stream
  }

  async add(frame: AnnexBFrame): Promise<void> {
    if (!this.started) {
      this.started = true
      await this.packets.add(packetOf(frame), decoderMeta(this.info))
      return
    }
    await this.packets.add(packetOf(frame))
  }

  async finalize(): Promise<Blob> {
    this.packets.close()
    if (this.output.state === 'started') {
      await this.output.finalize()
    }
    const { buffer } = this.target
    if (!buffer) {
      throw new Error('No video frames to mux.')
    }
    return new Blob([buffer], { type: 'video/mp4' })
  }
}
