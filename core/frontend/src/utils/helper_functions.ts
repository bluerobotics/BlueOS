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
