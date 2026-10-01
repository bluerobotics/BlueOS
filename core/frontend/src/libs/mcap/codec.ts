/**
 * Annex B helpers that mediabunny does not expose: NAL splitting, keyframe detection, and
 * prepending cached parameter sets for recordings that only send them once.
 *
 * SPS/PPS parsing is mediabunny's (see probeDecoderInfo). AVCC/HVCC is written when it muxes.
 */
export type VideoFormat = 'h264' | 'h265'

const START_CODE = new Uint8Array([0, 0, 0, 1])
const H264_NAL_SLICE_IDR = 5
const H264_NAL_SPS = 7
const H264_NAL_PPS = 8
const H265_NAL_VPS = 32
const H265_NAL_SPS = 33
const H265_NAL_PPS = 34
const H265_IRAP_RANGE = [16, 23]

export interface NalUnit {
  offset: number
  length: number
  type: number
}

export function videoCodecId(format: VideoFormat): 'avc' | 'hevc' {
  return format === 'h265' ? 'hevc' : 'avc'
}

/** Splits an Annex B buffer into NAL units, skipping the start codes. */
export function iterateNalUnits(data: Uint8Array, isH265: boolean): NalUnit[] {
  const units: NalUnit[] = []
  let start = -1

  function pushUnit(end: number): void {
    if (start < 0 || end <= start) {
      return
    }
    let length = end - start
    while (length > 0 && data[start + length - 1] === 0) {
      length -= 1
    }
    if (length > 0) {
      const header = data[start]
      units.push({ offset: start, length, type: isH265 ? header >> 1 & 0x3f : header & 0x1f })
    }
  }

  let index = 0
  while (index + 2 < data.length) {
    if (data[index] === 0 && data[index + 1] === 0 && data[index + 2] === 1) {
      pushUnit(index)
      index += 3
      start = index
    } else {
      index += 1
    }
  }
  pushUnit(data.length)
  return units
}

function isKeyframeNal(type: number, isH265: boolean): boolean {
  return isH265 ? type >= H265_IRAP_RANGE[0] && type <= H265_IRAP_RANGE[1] : type === H264_NAL_SLICE_IDR
}

export function isKeyframe(frame: Uint8Array, format: VideoFormat): boolean {
  const isH265 = format === 'h265'
  return iterateNalUnits(frame, isH265).some(({ type }) => isKeyframeNal(type, isH265))
}

/** AVCC/HVCC access unit: 4-byte length prefixes, which is what WebCodecs wants. */
export function annexBToLengthPrefixed(data: Uint8Array, format: VideoFormat): Uint8Array {
  const units = iterateNalUnits(data, format === 'h265')
  let size = 0
  for (const unit of units) {
    size += 4 + unit.length
  }
  const output = new Uint8Array(size)
  let offset = 0
  for (const unit of units) {
    output[offset] = unit.length >> 24 & 0xff
    output[offset + 1] = unit.length >> 16 & 0xff
    output[offset + 2] = unit.length >> 8 & 0xff
    output[offset + 3] = unit.length & 0xff
    output.set(data.subarray(unit.offset, unit.offset + unit.length), offset + 4)
    offset += 4 + unit.length
  }
  return output
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

  /**
   * Annex B access unit with parameter sets in-band, which is what mediabunny needs when muxing
   * without an avcC/hvcC description.
   */
  withParameterSets(frame: Uint8Array, format: VideoFormat): Uint8Array {
    this.observeFrame(frame, format)
    if (!this.complete) {
      return frame
    }
    const isH265 = format === 'h265'
    const types = new Set(iterateNalUnits(frame, isH265).map((unit) => unit.type))
    const missing = isH265
      ? [H265_NAL_VPS, H265_NAL_SPS, H265_NAL_PPS].filter((type) => !types.has(type))
      : [H264_NAL_SPS, H264_NAL_PPS].filter((type) => !types.has(type))
    if (missing.length === 0) {
      return frame
    }

    const prefixNals: Uint8Array[] = []
    for (const type of missing) {
      if (type === H265_NAL_VPS) {
        prefixNals.push(...this.vps)
      } else if (type === H264_NAL_SPS || type === H265_NAL_SPS) {
        prefixNals.push(...this.sps)
      } else {
        prefixNals.push(...this.pps)
      }
    }
    let size = frame.length
    for (const nal of prefixNals) {
      size += START_CODE.length + nal.length
    }
    const output = new Uint8Array(size)
    let offset = 0
    for (const nal of prefixNals) {
      output.set(START_CODE, offset)
      output.set(nal, offset + START_CODE.length)
      offset += START_CODE.length + nal.length
    }
    output.set(frame, offset)
    return output
  }
}
