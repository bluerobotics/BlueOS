// Singleton library for error message emitter

class ErrorMessageManager {
  private static instance: ErrorMessageManager;

  callbacks: ((message: string) => void)[] = [(message: string) => { console.error(`Error: ${message}`) }]

  /**
   * Singleton access
   * @returns ErrorMessageManager
   */
  public static getInstance(): ErrorMessageManager {
    if (!ErrorMessageManager.instance) {
      ErrorMessageManager.instance = new ErrorMessageManager()
    }
    return ErrorMessageManager.instance
  }

  /**
   * Add callback to be used when a new message is received
   */
  addCallback(callback:(msg: string) => void): void {
    this.callbacks.push(callback)
  }

  /**
   * Emit a new message to be used in all callbacks
   */
  emitMessage(message: string): void {
    for (const callback of this.callbacks) {
      callback(message)
    }
  }
}

// Define public instance of singleton
const error_message_manager = ErrorMessageManager.getInstance()

export default error_message_manager
