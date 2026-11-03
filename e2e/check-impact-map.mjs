#!/usr/bin/env bun
// Fails when impact-map.json and the spec tags disagree.
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const e2eDir = path.dirname(fileURLToPath(import.meta.url))
const read = (file) => readFileSync(path.join(e2eDir, file), 'utf8')

const map = JSON.parse(read('impact-map.json'))
const mapTags = new Set(map.rules.flatMap((rule) => rule.tags).filter((tag) => tag !== '*'))

const specTags = new Map()
const pagesDir = path.join(e2eDir, 'tests', 'pages')
for (const file of readdirSync(pagesDir)) {
  const source = readFileSync(path.join(pagesDir, file), 'utf8')
  for (const match of source.matchAll(/tag:\s*'(@[\w-]+)'/g)) {
    specTags.set(match[1], file)
  }
}

const errors = []
for (const [tag, file] of specTags) {
  if (!mapTags.has(tag)) errors.push(`${file}: ${tag} has no rule in impact-map.json`)
}

if (errors.length) {
  console.error(errors.join('\n'))
  process.exit(1)
}
console.log(`impact map ok: ${specTags.size} tags`)
