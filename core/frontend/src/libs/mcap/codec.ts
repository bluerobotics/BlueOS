/**
 * Turns Annex B video frames from `foxglove.CompressedVideo` messages into everything the MP4 muxer
 * needs: sample data in AVCC/HVCC form, frame dimensions and the decoder configuration record.
 */
import { BitReader, iterateNalUnits, unescapeRbsp } from './bitstream'

export type VideoFormat = 'h264' | 'h265'

export interface CodecConfig {
  /** MP4 sample entry box, e.g. `avc1` or `hvc1`. */
  sampleEntry: string
  /** Codec string for the MSE mime type, e.g. `avc1.42e01e`. */
  codec: string
  width: number
  height: number
  /** avcC / hvcC payload, embedded in the sample entry and reused as the WebCodecs description. */
  description: Uint8Array
}

const H264_NAL_SLICE_IDR = 5
const H264_NAL_SPS = 7
const H264_NAL_PPS = 8
const H265_NAL_VPS = 32
const H265_NAL_SPS = 33
const H265_NAL_PPS = 34
const H265_IRAP_RANGE = [16, 23]
const HIGH_PROFILES = [100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135]

function toHex(value: number, digits = 2): string {
  return value.toString(16).padStart(digits, '0')
}

function skipScalingList(reader: BitReader, size: number): void {
  let lastScale = 8
  let nextScale = 8
  for (let index = 0; index < size; index += 1) {
    if (nextScale !== 0) {
      nextScale = (lastScale + reader.se() + 256) % 256
    }
    lastScale = nextScale === 0 ? lastScale : nextScale
  }
}

function parseH264Sps(nal: Uint8Array): { width: number, height: number } {
  const reader = new BitReader(unescapeRbsp(nal.subarray(1)))
  const profileIdc = reader.bits(8)
  reader.skipBits(16) // constraint flags + level_idc
  reader.ue() // seq_parameter_set_id

  let chromaFormatIdc = 1
  if (HIGH_PROFILES.includes(profileIdc)) {
    chromaFormatIdc = reader.ue()
    if (chromaFormatIdc === 3) {
      reader.skipBits(1) // separate_colour_plane_flag
    }
    reader.ue() // bit_depth_luma_minus8
    reader.ue() // bit_depth_chroma_minus8
    reader.skipBits(1) // qpprime_y_zero_transform_bypass_flag
    if (reader.bit() === 1) {
      const lists = chromaFormatIdc !== 3 ? 8 : 12
      for (let index = 0; index < lists; index += 1) {
        if (reader.bit() === 1) {
          skipScalingList(reader, index < 6 ? 16 : 64)
        }
      }
    }
  }

  reader.ue() // log2_max_frame_num_minus4
  const picOrderCntType = reader.ue()
  if (picOrderCntType === 0) {
    reader.ue() // log2_max_pic_order_cnt_lsb_minus4
  } else if (picOrderCntType === 1) {
    reader.skipBits(1) // delta_pic_order_always_zero_flag
    reader.se() // offset_for_non_ref_pic
    reader.se() // offset_for_top_to_bottom_field
    const cycleLength = reader.ue()
    for (let index = 0; index < cycleLength; index += 1) {
      reader.se() // offset_for_ref_frame
    }
  }

  reader.ue() // max_num_ref_frames
  reader.skipBits(1) // gaps_in_frame_num_value_allowed_flag
  const widthInMbs = reader.ue() + 1
  const heightInMapUnits = reader.ue() + 1
  const frameMbsOnlyFlag = reader.bit()
  if (frameMbsOnlyFlag === 0) {
    reader.skipBits(1) // mb_adaptive_frame_field_flag
  }
  reader.skipBits(1) // direct_8x8_inference_flag

  let cropLeft = 0
  let cropRight = 0
  let cropTop = 0
  let cropBottom = 0
  if (reader.bit() === 1) {
    cropLeft = reader.ue()
    cropRight = reader.ue()
    cropTop = reader.ue()
    cropBottom = reader.ue()
  }

  const subWidth = chromaFormatIdc === 3 ? 1 : 2
  const subHeight = chromaFormatIdc === 1 ? 2 : 1
  const cropUnitX = chromaFormatIdc === 0 ? 1 : subWidth
  const cropUnitY = (chromaFormatIdc === 0 ? 1 : subHeight) * (2 - frameMbsOnlyFlag)

  return {
    width: widthInMbs * 16 - cropUnitX * (cropLeft + cropRight),
    height: (2 - frameMbsOnlyFlag) * heightInMapUnits * 16 - cropUnitY * (cropTop + cropBottom),
  }
}

function buildAvcC(sps: Uint8Array, pps: Uint8Array): Uint8Array {
  const record = new Uint8Array(11 + sps.length + pps.length)
  const view = new DataView(record.buffer)
  const [, profileIdc, profileCompatibility, levelIdc] = sps
  record[0] = 1
  record[1] = profileIdc
  record[2] = profileCompatibility
  record[3] = levelIdc
  record[4] = 0xff // 6 reserved bits + lengthSizeMinusOne = 3
  record[5] = 0xe1 // 3 reserved bits + one SPS
  view.setUint16(6, sps.length)
  record.set(sps, 8)
  record[8 + sps.length] = 1
  view.setUint16(9 + sps.length, pps.length)
  record.set(pps, 11 + sps.length)
  return record
}

interface H265SpsInfo {
  width: number
  height: number
  profileSpace: number
  tierFlag: number
  profileIdc: number
  compatibilityFlags: number
  constraintBytes: Uint8Array
  levelIdc: number
  chromaFormatIdc: number
  bitDepthLuma: number
  bitDepthChroma: number
  maxSubLayersMinus1: number
  temporalIdNesting: number
}

function parseH265Sps(nal: Uint8Array): H265SpsInfo {
  const payload = unescapeRbsp(nal.subarray(2))
  const reader = new BitReader(payload)
  reader.skipBits(4) // sps_video_parameter_set_id
  const maxSubLayersMinus1 = reader.bits(3)
  const temporalIdNesting = reader.bit()

  // profile_tier_level: the general block is a fixed 12 bytes we can copy straight into hvcC.
  const profileSpace = reader.bits(2)
  const tierFlag = reader.bit()
  const profileIdc = reader.bits(5)
  let compatibilityFlags = 0
  for (let index = 0; index < 32; index += 1) {
    compatibilityFlags = (compatibilityFlags << 1 | reader.bit()) >>> 0
  }
  const constraintBytes = new Uint8Array(6)
  for (let index = 0; index < 6; index += 1) {
    constraintBytes[index] = reader.bits(8)
  }
  const levelIdc = reader.bits(8)

  const profilePresent: number[] = []
  const levelPresent: number[] = []
  for (let index = 0; index < maxSubLayersMinus1; index += 1) {
    profilePresent.push(reader.bit())
    levelPresent.push(reader.bit())
  }
  if (maxSubLayersMinus1 > 0) {
    reader.skipBits(2 * (8 - maxSubLayersMinus1))
  }
  for (let index = 0; index < maxSubLayersMinus1; index += 1) {
    if (profilePresent[index] === 1) {
      reader.skipBits(88)
    }
    if (levelPresent[index] === 1) {
      reader.skipBits(8)
    }
  }

  reader.ue() // sps_seq_parameter_set_id
  const chromaFormatIdc = reader.ue()
  if (chromaFormatIdc === 3) {
    reader.skipBits(1) // separate_colour_plane_flag
  }
  const widthInSamples = reader.ue()
  const heightInSamples = reader.ue()
  let cropLeft = 0
  let cropRight = 0
  let cropTop = 0
  let cropBottom = 0
  if (reader.bit() === 1) {
    cropLeft = reader.ue()
    cropRight = reader.ue()
    cropTop = reader.ue()
    cropBottom = reader.ue()
  }
  const bitDepthLuma = reader.ue() + 8
  const bitDepthChroma = reader.ue() + 8

  const subWidth = chromaFormatIdc === 1 || chromaFormatIdc === 2 ? 2 : 1
  const subHeight = chromaFormatIdc === 1 ? 2 : 1

  return {
    width: widthInSamples - subWidth * (cropLeft + cropRight),
    height: heightInSamples - subHeight * (cropTop + cropBottom),
    profileSpace,
    tierFlag,
    profileIdc,
    compatibilityFlags,
    constraintBytes,
    levelIdc,
    chromaFormatIdc,
    bitDepthLuma,
    bitDepthChroma,
    maxSubLayersMinus1,
    temporalIdNesting,
  }
}

function buildHvcC(info: H265SpsInfo, arrays: { type: number, nals: Uint8Array[] }[]): Uint8Array {
  const bytes: number[] = []
  function pushUint16(value: number): void {
    bytes.push(value >> 8 & 0xff, value & 0xff)
  }

  bytes.push(1)
  bytes.push((info.profileSpace & 3) << 6 | (info.tierFlag & 1) << 5 | info.profileIdc & 0x1f)
  bytes.push(
    info.compatibilityFlags >>> 24 & 0xff,
    info.compatibilityFlags >>> 16 & 0xff,
    info.compatibilityFlags >>> 8 & 0xff,
    info.compatibilityFlags & 0xff,
  )
  bytes.push(...info.constraintBytes)
  bytes.push(info.levelIdc)
  pushUint16(0xf000) // reserved + min_spatial_segmentation_idc
  bytes.push(0xfc) // reserved + parallelismType
  bytes.push(0xfc | info.chromaFormatIdc & 3)
  bytes.push(0xf8 | info.bitDepthLuma - 8 & 7)
  bytes.push(0xf8 | info.bitDepthChroma - 8 & 7)
  pushUint16(0) // avgFrameRate, unknown
  bytes.push(
    info.maxSubLayersMinus1 + 1 << 3 | (info.temporalIdNesting & 1) << 2 | 3,
  )
  bytes.push(arrays.length)
  for (const array of arrays) {
    bytes.push(0x80 | array.type & 0x3f)
    pushUint16(array.nals.length)
    for (const nal of array.nals) {
      pushUint16(nal.length)
      bytes.push(...nal)
    }
  }
  return new Uint8Array(bytes)
}

function h265CodecString(info: H265SpsInfo): string {
  let reversed = 0
  for (let index = 0; index < 32; index += 1) {
    reversed = (reversed << 1 | info.compatibilityFlags >>> index & 1) >>> 0
  }
  const space = ['', 'A', 'B', 'C'][info.profileSpace]
  const tier = info.tierFlag === 1 ? 'H' : 'L'
  const constraints = [...info.constraintBytes]
  while (constraints.length > 0 && constraints[constraints.length - 1] === 0) {
    constraints.pop()
  }
  const suffix = constraints.map((byte) => `.${toHex(byte).toUpperCase()}`).join('')
  return `hvc1.${space}${info.profileIdc}.${reversed.toString(16)}.${tier}${info.levelIdc}${suffix}`
}

function isKeyframeNal(type: number, isH265: boolean): boolean {
  return isH265 ? type >= H265_IRAP_RANGE[0] && type <= H265_IRAP_RANGE[1] : type === H264_NAL_SLICE_IDR
}

export function isKeyframe(frame: Uint8Array, format: VideoFormat): boolean {
  const isH265 = format === 'h265'
  return iterateNalUnits(frame, isH265).some(({ type }) => isKeyframeNal(type, isH265))
}

/**
 * Keeps the most recent parameter sets seen in a stream.
 *
 * Foxglove requires keyframes to carry their parameter sets, which is what makes seeking into the
 * middle of a recording possible, but some older recordings only send them once at the start of the
 * stream. Remembering them lets those recordings play too.
 */
export class ParameterSetCache {
  private vps: Uint8Array[] = []

  private sps: Uint8Array[] = []

  private pps: Uint8Array[] = []

  observe(type: number, nal: Uint8Array, format: VideoFormat): void {
    if (format === 'h265') {
      switch (type) {
        case H265_NAL_VPS: this.vps = [nal]; break
        case H265_NAL_SPS: this.sps = [nal]; break
        case H265_NAL_PPS: this.pps = [nal]; break
        default: break
      }
      return
    }
    if (type === H264_NAL_SPS) {
      this.sps = [nal]
    } else if (type === H264_NAL_PPS) {
      this.pps = [nal]
    }
  }

  observeFrame(frame: Uint8Array, format: VideoFormat): void {
    for (const unit of iterateNalUnits(frame, format === 'h265')) {
      this.observe(unit.type, frame.subarray(unit.offset, unit.offset + unit.length), format)
    }
  }

  get complete(): boolean {
    return this.sps.length > 0 && this.pps.length > 0
  }

  buildConfig(format: VideoFormat): CodecConfig | null {
    if (!this.complete) {
      return null
    }
    const [sps] = this.sps
    if (format === 'h264') {
      const { width, height } = parseH264Sps(sps)
      return {
        sampleEntry: 'avc1',
        codec: `avc1.${toHex(sps[1])}${toHex(sps[2])}${toHex(sps[3])}`,
        width,
        height,
        description: buildAvcC(sps, this.pps[0]),
      }
    }

    const info = parseH265Sps(sps)
    const arrays = [
      { type: H265_NAL_VPS, nals: this.vps },
      { type: H265_NAL_SPS, nals: this.sps },
      { type: H265_NAL_PPS, nals: this.pps },
    ].filter((array) => array.nals.length > 0)
    return {
      sampleEntry: 'hvc1',
      codec: h265CodecString(info),
      width: info.width,
      height: info.height,
      description: buildHvcC(info, arrays),
    }
  }
}

/**
 * Converts Annex B start codes into the 4 byte length prefixes MP4 samples use, reporting whether
 * the frame can be decoded on its own and collecting any parameter sets it carries.
 */
export function toMp4Sample(
  frame: Uint8Array,
  format: VideoFormat,
  parameterSets?: ParameterSetCache,
): { data: Uint8Array, isKeyframe: boolean } {
  const isH265 = format === 'h265'
  const units = iterateNalUnits(frame, isH265)
  const size = units.reduce((total, unit) => total + unit.length + 4, 0)
  const data = new Uint8Array(size)
  const view = new DataView(data.buffer)
  let offset = 0
  let keyframe = false
  for (const unit of units) {
    const nal = frame.subarray(unit.offset, unit.offset + unit.length)
    view.setUint32(offset, unit.length)
    data.set(nal, offset + 4)
    offset += unit.length + 4
    keyframe = keyframe || isKeyframeNal(unit.type, isH265)
    parameterSets?.observe(unit.type, nal, format)
  }
  return { data, isKeyframe: keyframe }
}
