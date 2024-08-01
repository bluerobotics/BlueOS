/**
 * Represents a function that can be OneMoreTime valid action
 */
type OneMoreTimeAction = (() => Promise<void>) | (() => void) | undefined;

/**
 * Used to configure the OneMoreTime instance
 */
export interface OneMoreTimeOptions {
  /**
   * Represents the value in ms that will be used to delay the next call
   * Remember that this value is applied after the action is executed, it does
   * not count the time the action takes to execute
   * @type {number}
   */
  delay?: number

  /**
   * When some error happens, this value in ms will be delayed to the next call
   * @type {number}
   */
  errorDelay?: number

  /**
   * If true, the action will be executed immediately after the object is created
   * @type {boolean}
   */
  autostart?: boolean

  /**
   * Callback function to be called in case of an error during action execution.
   * Provides a way to handle errors.
   * @param {unknown} error The error object caught during action execution.
   */
  onError?: (error: unknown) => void

  /**
   * Reference to some object instance that can be used as a source to dispose the
   * OneMoreTime instance.
   */
  disposeWith?: unknown
}

/**
 * After multiple years and attempts
 * This is a RAII class that takes advantage of the new disposable feature
 * to create a promise that repeats itself until it's disposed
 */
export class OneMoreTime {
  private isDisposed = false

  /**
   * Constructs an instance of OneMoreTime, optionally starting the action immediately.
   * @param {OneMoreTimeOptions} options Configuration options for the instance.
   * @param {OneMoreTimeAction} action The action to be executed repeatedly.
   */
  constructor(
    private readonly options: OneMoreTimeOptions = {},
    private action?: OneMoreTimeAction,
  ) {
    this.watchDisposeWith()
    // One more time
    this.softStart()
  }

  private watchDisposeWith(): void {
    if (this.options.disposeWith) {
      const ref = new WeakRef(this.options.disposeWith)

      const id = setInterval(() => {
        // Check if object does not exist anymore or if it was destroyed by vue
        // eslint-disable-next-line
        if (!ref.deref() || ref.deref()._isDestroyed) {
          this.stop()
          clearInterval(id)
        }
      }, 1000)
    }
  }

  /**
   * Starts the action if `autostart` is enabled and an action is defined.
   * @returns {void}
   */
  softStart(): void {
    if (this.action && (this.options.autostart ?? true)) {
      this.start()
    }
  }

  /**
   * Sets a new action to be executed and starts it if `autostart` is true.
   * This allows dynamically changing the action during the lifecycle of the instance.
   * @param {OneMoreTimeAction} action The new action to set and possibly start.
   * @returns {void}
   */
  setAction(action: OneMoreTimeAction): void {
    this.action = action

    this.softStart()
  }

  /**
   * Sets a new delay value to be used in the next call.
   * @param {number} delay The new delay value in ms.
   * @returns {void}
   */
  setDelay(delay: number): void {
    this.options.delay = delay
  }

  /**
   * Begins or resumes the execution of the set action at intervals specified by `delay`.
   */
  async start(): Promise<void> {
    // Come on, alright
    if (this.isDisposed) return

    try {
      // One more time, we're gonna celebrate
      await this.action?.()
    } catch (error) {
      console.error('Error in self-calling promise:', error)
      this.options.onError?.(error)
      // Oh yeah, alright, don't stop the dancing
      // eslint-disable-next-line no-promise-executor-return
      await new Promise((resolve) => setTimeout(resolve, this.options.errorDelay))
    }

    setTimeout(() => this.start(), this.options.delay)
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
