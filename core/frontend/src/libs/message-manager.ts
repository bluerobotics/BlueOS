import { NotificationLevel as MessageLevel } from '@/types/notifications'

// Singleton library for message emitter

class MessageManager {
  private static instance: MessageManager

  callbacks: ((level: MessageLevel, message: string) => void)[] = [
    (message, level) => {
      switch (level) {
        case MessageLevel.Success:
          console.log(message)
          break
        case MessageLevel.Error:
          console.error(message)
          break
        case MessageLevel.Info:
          console.info(message)
          break
        case MessageLevel.Warning:
          console.warn(message)
          break
        case MessageLevel.Critical:
          console.error(message)
          break
        default:
          console.log(message)
          break
      }
    },
  ]

  /**
   * Singleton access
   * @returns MessageManager
   */
  public static getInstance(): MessageManager {
    if (!MessageManager.instance) {
      MessageManager.instance = new MessageManager()
    }
    return MessageManager.instance
  }

  /**
   * Add callback to be used when a new message is received
   */
  addCallback(callback:(level: MessageLevel, msg: string) => void): void {
    this.callbacks.push(callback)
  }

  /**
   * Emit a new message to be used in all callbacks
   */
  emitMessage(level: MessageLevel, message: string): void {
    for (const callback of this.callbacks) {
      callback(level, message)
    }
  }
}

// Define public instance of singleton
const message_manager = MessageManager.getInstance()

export { MessageLevel }
export default message_manager
