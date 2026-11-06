import '@/cosmos'

import {
  afterEach, beforeEach, describe, expect, it,
} from 'vitest'

import { loadBlueosVersion, parseBlueosVersion } from '@/utils/blueos-version'
import { convertGitDescribeToTag, convertGitDescribeToUrl } from '@/utils/helper_functions'

const PROJECT = 'https://github.com/bluerobotics/BlueOS'

describe('GIT_DESCRIBE_TAGS', () => {
  it('links a tag build to its release', () => {
    expect(convertGitDescribeToTag('1.4.0-0-gabcdef12')).toBe('1.4.0')
    expect(convertGitDescribeToUrl('1.4.0-0-gabcdef12')).toBe(`${PROJECT}/releases/tag/1.4.0`)
  })

  it('links commits after a tag to that commit', () => {
    expect(convertGitDescribeToTag('1.4.0-10-gabcdef12')).toBeUndefined()
    expect(convertGitDescribeToUrl('1.4.0-10-gabcdef12')).toBe(`${PROJECT}/tree/abcdef12`)
  })

  it('links an empty description to the project', () => {
    expect(convertGitDescribeToTag('')).toBeUndefined()
    expect(convertGitDescribeToUrl('')).toBe(PROJECT)
  })
})

describe('blueos-version file', () => {
  it('reads the description and the committer time', () => {
    const committer_time = '2026-10-05T18:00:00Z'
    const parsed = parseBlueosVersion(`1.4.0-10-gabcdef12\n${committer_time}\n`)
    expect(parsed.git_describe).toBe('1.4.0-10-gabcdef12')
    expect(parsed.build_date).toBe(new Date(committer_time).toLocaleString())
  })

  it('keeps the description when the file has no date', () => {
    const parsed = parseBlueosVersion('1.4.0-0-gabcdef12\n')
    expect(parsed.git_describe).toBe('1.4.0-0-gabcdef12')
    expect(parsed.build_date).toBe('')
  })

  it('ignores a body that is not a git description', () => {
    const parsed = parseBlueosVersion('not a describe line')
    expect(parsed.git_describe).toBe('')
    expect(parsed.build_date).toBe('')
  })

  it('reads a file with CRLF line endings', () => {
    const parsed = parseBlueosVersion('1.4.0-10-gabcdef12\r\n2026-10-05T18:00:00Z\r\n')
    expect(parsed.git_describe).toBe('1.4.0-10-gabcdef12')
    expect(parsed.build_date).not.toBe('')
  })
})

describe('loadBlueosVersion', () => {
  const original_fetch = globalThis.fetch
  const original_console_error = console.error

  beforeEach(() => {
    console.error = () => undefined
  })

  afterEach(() => {
    globalThis.fetch = original_fetch
    console.error = original_console_error
  })

  it('stays empty when the request fails, even after an earlier success', async () => {
    globalThis.fetch = async () => ({ ok: true, text: async () => '1.4.0-10-gabcdef12\n' }) as Response
    expect(await loadBlueosVersion()).toBe('1.4.0-10-gabcdef12')
    globalThis.fetch = async () => { throw new Error('offline') }
    expect(await loadBlueosVersion()).toBe('')
  })

  it('stays empty on a non-OK response', async () => {
    globalThis.fetch = async () => ({ ok: false }) as Response
    expect(await loadBlueosVersion()).toBe('')
  })

  it('returns the description the image serves', async () => {
    globalThis.fetch = async () => ({ ok: true, text: async () => '1.4.0-10-gabcdef12\n' }) as Response
    expect(await loadBlueosVersion()).toBe('1.4.0-10-gabcdef12')
  })
})
