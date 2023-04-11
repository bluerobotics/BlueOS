/* Asynchronously wait for a given interval. */
/**
 * @param interval - Time in milliseconds to wait after the previous request is done
* */
export function sleep(interval: number): Promise<number> {
  // eslint-disable-next-line no-promise-executor-return
  return new Promise((resolve) => setTimeout(resolve, interval))
}

const periodic_tasks_counter: Map<() => Promise<void>, number> = new Map()

/* Call a given function periodically for a given interval. */
/**
 * @param func - Function to be called.
 * @param interval - Time in milliseconds to wait after the previous request is done
* */
export async function callPeriodically(
  func: () => Promise<void>,
  interval: number,
  automated_call?: boolean,
): Promise<void> {
  let current_count = periodic_tasks_counter.get(func) ?? 0
  if (!automated_call) {
    current_count += 1
    periodic_tasks_counter.set(func, current_count)
  }
  if (current_count <= 0) {
    periodic_tasks_counter.set(func, 0)
    return
  }
  await func()
  await sleep(interval)
  callPeriodically(func, interval, true)
}

/* Stop Callingg a given function periodically. */
/**
 * @param function_name - Function to be called.
* */
export function stopCallingPeriodically(func: () => Promise<void>): void {
  const current_count = periodic_tasks_counter.get(func) ?? 1
  periodic_tasks_counter.set(func, current_count - 1)
}

/* Cast a string into a proper javascript type. */
/**
 * @param value - String to be cast
* */
export function castString(value: string): any { // eslint-disable-line @typescript-eslint/no-explicit-any
  if (typeof value !== 'string') {
    return value
  }

  try {
    return JSON.parse(value)
  } catch (error) {
    // If there's an error, assume it's just a string.
  }

  return value
}

/* Convert git describe text to a valid URL for the project. */
/**
 * @param func - Function to be called.
 * @param interval - Time in milliseconds to wait after the previous request is done
* */
export function convertGitDescribeToUrl(git_describe: string): string {
  const user = 'bluerobotics'
  const repository = 'blueos-docker'
  const project_url = `https://github.com/${user}/${repository}`

  // Local development version, pointing to root page
  if (!git_describe || git_describe.endsWith('-dirty') || git_describe.isEmpty()) {
    return project_url
  }

  // Show tag release page
  if (git_describe.startsWith('tags')) {
    const match = /tags\/(?<tag>|.*)-\d-.*/gm.exec(git_describe)
    if (match && match.groups?.tag) {
      const { tag } = match.groups
      return `${project_url}/releases/tag/${tag}`
    }
  }

  // Show git source files page for commit
  // It follows: `-gHASH`, where there is no fixed size for HASH size
  const hash = /-g([0-9a-f]+)$/.exec(git_describe)?.[1]
  return `${project_url}/tree/${hash}`
}

export function prettifySize(size_kb: number): string {
  if (Number.isNaN(size_kb)) {
    return 'N/A'
  }
  if (size_kb < 1024) {
    return `${size_kb.toFixed(1)} kB`
  }
  const size_mb = size_kb / 1024
  if (size_mb < 1024) {
    return `${size_mb.toFixed(1)} MB`
  }
  const size_gb = size_mb / 1024
  return `${size_gb.toFixed(1)} GB`
}
