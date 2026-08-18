/* Asynchronously wait for a given interval. */
/**
 * @param interval - Time in milliseconds to wait after the previous request is done
* */
export function sleep(interval: number): Promise<number> {
  // eslint-disable-next-line no-promise-executor-return
  return new Promise((resolve) => setTimeout(resolve, interval))
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

/**
 * Converts a git describe string to a tag string if present
 * @param git_describe - The git describe string to convert
 * @returns The tag string if present, otherwise undefined
 */
export function convertGitDescribeToTag(git_describe: string): string | undefined {
  if (!git_describe || git_describe.endsWith('-dirty') || git_describe.isEmpty()) {
    return undefined
  }

  const match = /tags\/(?<tag>|.*)-\d-.*/gm.exec(git_describe)
  if (match && match.groups?.tag) {
    return match.groups.tag
  }
  return undefined
}

/* Convert git describe text to a valid URL for the project. */
/**
 * @param func - Function to be called.
 * @param interval - Time in milliseconds to wait after the previous request is done
* */
export function convertGitDescribeToUrl(git_describe: string): string {
  const user = 'bluerobotics'
  const repository = 'BlueOS'
  const project_url = `https://github.com/${user}/${repository}`

  // Local development version, pointing to root page
  if (!git_describe || git_describe.endsWith('-dirty') || git_describe.isEmpty()) {
    return project_url
  }

  // Show tag release page
  if (git_describe.startsWith('tags')) {
    const tag = convertGitDescribeToTag(git_describe)
    if (tag) {
      return `${project_url}/releases/tag/${tag}`
    }
  }

  // Show git source files page for commit
  // It follows: `-gHASH`, where there is no fixed size for HASH size
  const hash = /-g([0-9a-f]+)$/.exec(git_describe)?.[1]
  return `${project_url}/tree/${hash}`
}

// Prefix for nginx's caching reverse proxy (see core/tools/nginx/nginx.conf).
// A request to `/cache/<host>/<path>` is proxied by the vehicle to `https://<host>/<path>`.
const VEHICLE_PROXY_PREFIX = '/cache/'

async function fetchWithTimeout(url: string, timeout_ms: number): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout_ms)
  try {
    return await fetch(url, { signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

/**
 * Fetch a remote URL, trying the topside browser's own connection first and falling
 * back to routing the request through the vehicle's caching proxy when that fails.
 * This allows resources hosted outside BlueOS to be reached even when only the vehicle
 * (and not the computer running the frontend) has internet access.
 */
export async function fetchWithVehicleFallback(url: string, timeout_ms = 5000): Promise<Response> {
  try {
    const response = await fetchWithTimeout(url, timeout_ms)
    if (response.ok) {
      return response
    }
  } catch {
    // Direct fetch failed, fall through to the vehicle proxy below.
  }

  const proxied_url = VEHICLE_PROXY_PREFIX + url.replace(/^https?:\/\//, '')
  return fetchWithTimeout(proxied_url, timeout_ms)
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
