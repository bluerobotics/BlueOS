#!/usr/bin/env bun
// Picks the e2e tags affected by a git diff using impact-map.json.
//   bun select-tests.mjs [ref] [--staged] [--run]
// Prints the --grep expression, or runs playwright with it when --run is given.
import { execFileSync, spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const e2eDir = path.dirname(fileURLToPath(import.meta.url))
const repoDir = path.dirname(e2eDir)
const args = process.argv.slice(2)
const run = args.includes('--run')
const staged = args.includes('--staged')
const ref = args.find((arg) => !arg.startsWith('--')) ?? 'origin/1.4-dev'

const map = JSON.parse(readFileSync(path.join(e2eDir, 'impact-map.json'), 'utf8'))

function git(...gitArgs) {
  return execFileSync('git', gitArgs, { cwd: repoDir, encoding: 'utf8' }).split('\n').filter(Boolean)
}

const changed = staged
  ? git('diff', '--name-only', '--cached')
  : [...git('diff', '--name-only', ref), ...git('ls-files', '--others', '--exclude-standard')]

// A changed spec selects its own tag, so edits to the tests themselves are picked up too
function specTags(file) {
  const filePath = path.join(repoDir, file)
  if (!existsSync(filePath)) return []
  const source = readFileSync(filePath, 'utf8')
  return [...source.matchAll(/tag:\s*'(@[\w-]+)'/g)].map((match) => match[1])
}

const tags = new Set()
let full = false
for (const file of new Set(changed)) {
  const isSource = (file.startsWith('core/frontend/') || file.startsWith('e2e/')) && !file.endsWith('.md')
  if (!isSource) continue
  if (/^e2e\/tests\/.*\.spec\.ts$/.test(file) && file !== 'e2e/tests/seed.spec.ts') {
    specTags(file).forEach((tag) => tags.add(tag))
    continue
  }
  const rule = map.rules.find((candidate) => path.matchesGlob(file, candidate.match))
  if (!rule) {
    console.error(`unmatched: ${file} → running full suite`)
    full = true
    continue
  }
  rule.tags.forEach((tag) => tags.add(tag))
}
if (tags.has('*')) full = true

const grep = full ? null : [...tags].sort().join('|')
if (!full && !grep) {
  console.log('no frontend changes, nothing to run')
  process.exit(0)
}
if (!run) {
  console.log(full ? 'full suite' : `--grep "${grep}"`)
  process.exit(0)
}

const playwrightArgs = ['playwright', 'test', '--config', 'playwright.config.ts']
if (grep) playwrightArgs.push('--grep', grep)
const result = spawnSync('bunx', playwrightArgs, { cwd: e2eDir, stdio: 'inherit' })
process.exit(result.status ?? 1)
