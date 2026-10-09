import {
  closeSync,
  openSync,
  readSync,
  statSync,
} from 'fs'

import { ByteSource } from '../src/libs/mcap/source'

export default class FileSource implements ByteSource {
  bytesRead = 0

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
    return new Uint8Array(buffer.buffer, buffer.byteOffset, read)
  }

  close(): void {
    closeSync(this.fd)
  }
}
