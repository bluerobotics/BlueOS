/** Time between progress updates, so a long read does not repaint the page on every record. */
export const PROGRESS_INTERVAL_MS = 200

/** Returns true when enough time has passed to report progress, or when `force` is set. */
export function createProgressGate(intervalMs = PROGRESS_INTERVAL_MS): (force?: boolean) => boolean {
  let lastAt = 0
  return (force = false) => {
    const now = Date.now()
    if (!force && now - lastAt < intervalMs) {
      return false
    }
    lastAt = now
    return true
  }
}
