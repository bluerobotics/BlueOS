declare module 'lz4js' {
  export function decompress(source: Uint8Array, maxSize?: number): Uint8Array
  export function decompressBlock(
    source: Uint8Array,
    destination: Uint8Array,
    sourceIndex: number,
    sourceLength: number,
    destinationIndex: number,
  ): number
}
