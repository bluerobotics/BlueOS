/** Annex B bitstream helpers shared by the H.264 and H.265 parsers. */

export interface NalUnit {
  offset: number
  length: number
  /** NAL unit type, already shifted according to the codec's header layout. */
  type: number
}

/** Splits an Annex B buffer into NAL units, skipping the start codes. */
export function iterateNalUnits(data: Uint8Array, isH265: boolean): NalUnit[] {
  const units: NalUnit[] = []
  let start = -1

  function pushUnit(end: number): void {
    if (start < 0 || end <= start) {
      return
    }
    // Trailing zero bytes belong to the next start code, not to the payload.
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

/** Removes emulation prevention bytes so the payload can be read as a raw bit sequence. */
export function unescapeRbsp(data: Uint8Array): Uint8Array {
  const output = new Uint8Array(data.length)
  let written = 0
  let zeros = 0
  for (let index = 0; index < data.length; index += 1) {
    const byte = data[index]
    if (zeros === 2 && byte === 0x03) {
      zeros = 0
      continue
    }
    zeros = byte === 0 ? zeros + 1 : 0
    output[written] = byte
    written += 1
  }
  return output.subarray(0, written)
}

export class BitReader {
  private position = 0

  constructor(private data: Uint8Array) {}

  bit(): number {
    const byte = this.data[this.position >> 3] ?? 0
    const value = byte >> 7 - (this.position & 7) & 1
    this.position += 1
    return value
  }

  bits(count: number): number {
    let value = 0
    for (let index = 0; index < count; index += 1) {
      value = value * 2 + this.bit()
    }
    return value
  }

  /** Unsigned Exp-Golomb coded value. */
  ue(): number {
    let leadingZeros = 0
    while (this.bit() === 0 && leadingZeros < 32) {
      leadingZeros += 1
    }
    if (leadingZeros === 0) {
      return 0
    }
    return 2 ** leadingZeros - 1 + this.bits(leadingZeros)
  }

  /** Signed Exp-Golomb coded value. */
  se(): number {
    const value = this.ue()
    const magnitude = Math.ceil(value / 2)
    return value % 2 === 0 ? -magnitude : magnitude
  }

  skipBits(count: number): void {
    this.position += count
  }
}
