/** Random access byte source, so the MCAP reader can stay agnostic about where the bytes come from. */
export interface ByteSource {
  size(signal?: AbortSignal): Promise<number>
  read(offset: number, length: number, signal?: AbortSignal): Promise<Uint8Array>
  /** Bytes actually transferred so far, used to show the real cost of playback to the user. */
  readonly bytesRead: number
}

/** Bytes fetched from the end of the file to learn its size and read the MCAP footer at once. */
const TAIL_SIZE = 4096

export class HttpByteSource implements ByteSource {
  bytesRead = 0

  private total: number | null = null

  private tail: { offset: number, data: Uint8Array } | null = null

  constructor(public readonly url: string) {}

  async size(signal?: AbortSignal): Promise<number> {
    if (this.total === null) {
      await this.readTail(signal)
    }
    return this.total ?? 0
  }

  async read(offset: number, length: number, signal?: AbortSignal): Promise<Uint8Array> {
    if (length <= 0) {
      return new Uint8Array()
    }
    const cached = this.fromTail(offset, length)
    if (cached) {
      return cached
    }
    const { data } = await this.request(`bytes=${offset}-${offset + length - 1}`, signal)
    return data
  }

  private fromTail(offset: number, length: number): Uint8Array | null {
    if (!this.tail || offset < this.tail.offset || offset + length > this.tail.offset + this.tail.data.length) {
      return null
    }
    const start = offset - this.tail.offset
    return this.tail.data.subarray(start, start + length)
  }

  /** A suffix range tells us the total size and gives us the footer in a single request. */
  private async readTail(signal?: AbortSignal): Promise<void> {
    const { data, total } = await this.request(`bytes=-${TAIL_SIZE}`, signal)
    this.total = total
    this.tail = { offset: Math.max(0, total - data.length), data }
  }

  private async request(range: string, signal?: AbortSignal): Promise<{ data: Uint8Array, total: number }> {
    const response = await fetch(this.url, { headers: { Range: range }, signal })
    if (response.status !== 206) {
      // A 200 here means the whole file is on its way, which we must never do on a vehicle link.
      response.body?.cancel()
      throw new Error(`Recording server does not support range requests (got ${response.status}).`)
    }

    const total = Number(response.headers.get('content-range')?.split('/')?.[1])
    const data = new Uint8Array(await response.arrayBuffer())
    this.bytesRead += data.byteLength
    if (!Number.isFinite(total) || total <= 0) {
      throw new Error('Recording server did not report the file size.')
    }
    return { data, total }
  }
}
