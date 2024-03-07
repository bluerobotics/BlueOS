/**
 * After multiple years and attempts
 * This is a RAII class that takes advantage of the new disposable feature
 * to create a promise that repeats itself until it's disposed
 */
class OneMoreTime {
  private isDisposed = false

  constructor(
      private readonly action: () => Promise<void>,
      private readonly timeout = 5000,
      autostart = true,
  ) {
    // One more time
    if (autostart) {
      // eslint-disable-next-line no-return-await
      (async () => await this.start())()
    }
  }

  async start(): Promise<void> {
    // Come on, alright
    if (this.isDisposed) return

    try {
      // One more time, we're gonna celebrate
      await this.action()
    } catch (error) {
      console.error('Error in self-calling promise:', error)
      // Oh yeah, alright, don't stop the dancing
      // eslint-disable-next-line no-promise-executor-return
      await new Promise((resolve) => setTimeout(resolve, this.timeout))
    }

    // One more time, a celebration
    // eslint-disable-next-line no-return-await
    (async () => await this.start())()
  }

  // Celebrate and dance so free
  [Symbol.dispose](): void {
    this.stop()
  }

  // Stop timer
  stop(): void {
    this.isDisposed = true
  }
}

/** Example
    async function logTimestamp() {
        console.log('Current timestamp:', new Date())
        await new Promise(resolve => setTimeout(resolve, 1000)) // Simulate some async work
    }

    (async () => {
        console.log("started")
        using task = new OneMoreTime(logTimestamp)
        await new Promise(resolve => setTimeout(resolve, 5000)) // Simulate some async work
        console.log("done")
    })()
*/
