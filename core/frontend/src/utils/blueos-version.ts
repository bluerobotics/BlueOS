import Vue from 'vue'

import { sleep } from '@/utils/helper_functions'

const VERSION_PATH = '/blueos-version'
const FETCH_TIMEOUT_MS = 5000
// Same format the Dockerfile validates for GIT_DESCRIBE_TAGS.
const DESCRIBE_PATTERN = /-\d+-g[0-9a-f]{8,}$/

interface BlueosVersion {
  git_describe: string
  commit_date: string
}

const state = Vue.observable<BlueosVersion>({ git_describe: '', commit_date: '' })

export function blueosGitDescribe(): string {
  return state.git_describe
}

export function blueosCommitDate(): string {
  return state.commit_date
}

// First line is GIT_DESCRIBE_TAGS. Second line, when present, is the committer
// time of that commit (`git log -1 --format=%cI`).
export function parseBlueosVersion(body: string): BlueosVersion {
  const [describeLine, dateLine] = body.trim().split(/\r?\n/)
  const parsedDate = dateLine ? Date.parse(dateLine) : Number.NaN
  return {
    git_describe: describeLine && DESCRIBE_PATTERN.test(describeLine) ? describeLine : '',
    commit_date: Number.isNaN(parsedDate) ? '' : new Date(parsedDate).toLocaleString(),
  }
}

// Keeps the last good value when a later request fails or answers with something that is not a version.
export async function loadBlueosVersion(): Promise<string> {
  // AbortSignal.timeout is missing from older browsers, which topside laptops may run
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
  try {
    const response = await fetch(VERSION_PATH, { cache: 'no-store', signal: controller.signal })
    if (response.ok) {
      const parsed = parseBlueosVersion(await response.text())
      // A body that is not a git description must not wipe the last good value either
      if (parsed.git_describe) {
        Object.assign(state, parsed)
      }
    }
  } catch (error) {
    // The timeout is expected on a slow boot, and the caller retries: it is not worth a console error
    if ((error as Error)?.name !== 'AbortError') {
      console.error('Failed to read BlueOS version', error)
    }
  } finally {
    clearTimeout(timer)
  }
  return state.git_describe
}

// Reads the version again after each delay until it is known, so a slow or failed first read still ends with a version
// (and with whatever the caller starts from it). Stops sleeping as soon as a read succeeded, here or elsewhere.
export async function retryBlueosVersion(
  delaysMs: number[],
  onVersion: (version: string) => void,
  sleepFn: (ms: number) => Promise<unknown> = sleep,
): Promise<void> {
  for (const delayMs of delaysMs) {
    if (state.git_describe) {
      return
    }
    // eslint-disable-next-line no-await-in-loop
    await sleepFn(delayMs)
    if (state.git_describe) {
      return
    }
    // eslint-disable-next-line no-await-in-loop
    onVersion(await loadBlueosVersion())
  }
}

// For tests: the state is a module-level singleton.
export function resetBlueosVersion(): void {
  Object.assign(state, { git_describe: '', commit_date: '' })
}
