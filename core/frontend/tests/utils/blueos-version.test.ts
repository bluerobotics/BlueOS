import {
  afterEach, beforeEach, describe, expect, it, mock,
} from 'bun:test'

import {
  loadBlueosVersion, parseBlueosVersion, resetBlueosVersion, retryBlueosVersion,
} from '@/utils/blueos-version'

const original_fetch = globalThis.fetch
const original_console_error = console.error

function serve(impl: () => Promise<unknown>): void {
  globalThis.fetch = mock(impl) as unknown as typeof fetch
}

function ok(body: string): () => Promise<unknown> {
  return async () => ({ ok: true, text: async () => body })
}

afterEach(() => {
  globalThis.fetch = original_fetch
  console.error = original_console_error
})

describe('blueos-version file', () => {
  it('reads the description and the committer time', () => {
    const committer_time = '2026-10-05T18:00:00Z'
    const parsed = parseBlueosVersion(`1.4.0-10-gabcdef12\n${committer_time}\n`)
    expect(parsed.git_describe).toBe('1.4.0-10-gabcdef12')
    expect(parsed.commit_date).toBe(new Date(committer_time).toLocaleString())
  })

  it('keeps the description when the file has no date', () => {
    const parsed = parseBlueosVersion('1.4.0-0-gabcdef12\n')
    expect(parsed.git_describe).toBe('1.4.0-0-gabcdef12')
    expect(parsed.commit_date).toBe('')
  })

  it('ignores a body that is not a git description', () => {
    const parsed = parseBlueosVersion('not a describe line')
    expect(parsed.git_describe).toBe('')
    expect(parsed.commit_date).toBe('')
  })

  it('reads a file with CRLF line endings', () => {
    const committer_time = '2026-10-05T18:00:00Z'
    const parsed = parseBlueosVersion(`1.4.0-10-gabcdef12\r\n${committer_time}\r\n`)
    expect(parsed.git_describe).toBe('1.4.0-10-gabcdef12')
    expect(parsed.commit_date).toBe(new Date(committer_time).toLocaleString())
  })

  it('reads a pre-release tag with a two-digit distance', () => {
    expect(parseBlueosVersion('1.5.0-beta.3-12-gabcdef12\n').git_describe).toBe('1.5.0-beta.3-12-gabcdef12')
  })
})

describe('loadBlueosVersion', () => {
  beforeEach(async () => {
    console.error = () => undefined
    // The module keeps the last good value, so start every test from a known one
    serve(ok('1.0.0-0-g0000000a\n'))
    await loadBlueosVersion()
  })

  it('returns the description the image serves', async () => {
    serve(ok('1.4.0-10-gabcdef12\n'))
    expect(await loadBlueosVersion()).toBe('1.4.0-10-gabcdef12')
  })

  it('passes an abort signal that has not fired yet', async () => {
    let signal: AbortSignal | undefined
    globalThis.fetch = mock(async (_url: string, init?: RequestInit) => {
      signal = init?.signal ?? undefined
      return { ok: true, text: async () => '1.4.0-10-gabcdef12\n' }
    }) as unknown as typeof fetch
    await loadBlueosVersion()
    expect(signal).toBeInstanceOf(AbortSignal)
    expect(signal?.aborted).toBe(false)
  })

  it('keeps the last version when a later request fails', async () => {
    serve(ok('1.4.0-10-gabcdef12\n'))
    expect(await loadBlueosVersion()).toBe('1.4.0-10-gabcdef12')
    serve(async () => { throw new Error('offline') })
    expect(await loadBlueosVersion()).toBe('1.4.0-10-gabcdef12')
  })

  it('keeps the last version when the response body is not a version', async () => {
    serve(ok('1.4.0-10-gabcdef12\n'))
    await loadBlueosVersion()
    serve(ok('<!doctype html>'))
    expect(await loadBlueosVersion()).toBe('1.4.0-10-gabcdef12')
  })

  it('keeps the last version on a non-OK response', async () => {
    serve(ok('1.4.0-10-gabcdef12\n'))
    await loadBlueosVersion()
    serve(async () => ({ ok: false }))
    expect(await loadBlueosVersion()).toBe('1.4.0-10-gabcdef12')
  })
})

describe('timeouts and retries', () => {
  beforeEach(resetBlueosVersion)

  it('stays quiet when the request times out', async () => {
    const errors: unknown[] = []
    console.error = (...args: unknown[]) => { errors.push(args) }
    serve(async () => { throw new DOMException('timed out', 'AbortError') })
    await loadBlueosVersion()
    expect(errors).toEqual([])
  })

  it('still reports other failures', async () => {
    const errors: unknown[] = []
    console.error = (...args: unknown[]) => { errors.push(args) }
    serve(async () => { throw new Error('offline') })
    await loadBlueosVersion()
    expect(errors.length).toBe(1)
  })

  it('stops sleeping once a read succeeds', async () => {
    console.error = () => undefined
    const delays: number[] = []
    const versions: string[] = []
    let calls = 0
    globalThis.fetch = mock(async () => {
      calls += 1
      if (calls < 2) {
        throw new Error('offline')
      }
      return { ok: true, text: async () => '1.7.0-0-gabcdef12\n' }
    }) as unknown as typeof fetch
    await retryBlueosVersion([1, 2, 3, 4], (version) => versions.push(version), async (ms) => { delays.push(ms) })
    expect(delays).toEqual([1, 2])
    expect(calls).toBe(2)
    expect(versions[versions.length - 1]).toBe('1.7.0-0-gabcdef12')
  })

  it('does not sleep or fetch when the version is already known', async () => {
    serve(ok('1.7.0-0-gabcdef12\n'))
    await loadBlueosVersion()
    const delays: number[] = []
    let calls = 0
    globalThis.fetch = mock(async () => { calls += 1; throw new Error('unexpected') }) as unknown as typeof fetch
    await retryBlueosVersion([1, 2], () => undefined, async (ms) => { delays.push(ms) })
    expect(delays).toEqual([])
    expect(calls).toBe(0)
  })
})
