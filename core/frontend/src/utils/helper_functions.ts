/* Asynchronously wait for a given interval. */
/**
 * @param interval - Time in milliseconds to wait after the previous request is done
* */
export function sleep(interval: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, interval))
}

/* Call a given function periodically for a given interval. */
/**
 * @param func - Function to be called.
 * @param interval - Time in milliseconds to wait after the previous request is done
* */
export async function callPeriodically(func: () => Promise<void>, interval: number): Promise<void> {
  await func()
  await sleep(interval)
  callPeriodically(func, interval)
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
