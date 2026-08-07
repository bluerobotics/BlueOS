import { readdirSync, readFileSync } from 'node:fs'
import { extname, join } from 'node:path'

const textExtensions = new Set([
  '.css',
  '.html',
  '.js',
  '.json',
  '.map',
  '.svg',
  '.txt',
  '.webmanifest',
  '.xml',
])
const decoder = new TextDecoder('utf-8', { fatal: true })
const root = process.argv[2] ?? 'dist'
let validatedFiles = 0

function validateDirectory(directory: string): void {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      validateDirectory(path)
      continue
    }
    if (!textExtensions.has(extname(entry.name))) {
      continue
    }

    const contents = readFileSync(path)
    if (contents.includes(0)) {
      throw new Error(`NUL byte found in generated frontend asset: ${path}`)
    }
    try {
      decoder.decode(contents)
    } catch {
      throw new Error(`Generated frontend asset is not valid UTF-8: ${path}`)
    }
    validatedFiles += 1
  }
}

validateDirectory(root)
console.log(`Validated ${validatedFiles} generated frontend assets.`)
