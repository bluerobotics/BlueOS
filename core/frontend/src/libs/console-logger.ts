import { Config, Encoding, Session } from '@eclipse-zenoh/zenoh-ts'

import frontend from '@/store/frontend'

/**
 * Compliant with FoxGlove LogLevel
 * https://docs.foxglove.dev/docs/visualization/message-schemas/log-level
 */
enum LogLevel {
  UNKNOWN = 0,
  DEBUG = 1,
  INFO = 2,
  WARNING = 3,
  ERROR = 4,
  FATAL = 5,
}

/**
 * Compliant with FoxGlove Log
 * https://docs.foxglove.dev/docs/visualization/message-schemas/log
 */
interface Log {
  timestamp: { sec: number; nsec: number }
  level: LogLevel
  message: string
  name: string
  file: string
  line: number
}

class ConsoleLogger {
  private session: Session | null = null

  private static readonly STACK_LINE_REGEX = /\(?([^\s()]+):(\d+):\d+\)?/

  private static readonly LOG_ENCODING = Encoding.fromString(Encoding.APPLICATION_JSON.toString())

  readonly originalConsole: {
    log: typeof console.log
    info: typeof console.info
    warn: typeof console.warn
    error: typeof console.error
    debug: typeof console.debug
  }

  constructor() {
    this.originalConsole = {
      log: console.log,
      info: console.info,
      warn: console.warn,
      error: console.error,
      debug: console.debug,
    }

    ConsoleLogger.LOG_ENCODING.withSchema('foxglove.Log')
  }

  async initialize(): Promise<void> {
    if (this.session !== null) {
      return
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${protocol}://${window.location.host}/zenoh-api/`
      const config = new Config(url)
      this.session = await Session.open(config)

      this.interceptConsole()
      this.interceptWindow()
    } catch (error) {
      console.error('[ConsoleLogger] Failed to initialize:', error)
    }
  }

  private readonly onError = (event: ErrorEvent): void => {
    this.publishMessage(
      LogLevel.ERROR,
      [event.message, event.filename, event.lineno, event.colno, event.error],
      event.filename,
      event.lineno,
    )
  }

  private readonly onUnhandledRejection = (event: PromiseRejectionEvent): void => {
    this.publishMessage(LogLevel.ERROR, [event.reason, event.promise, event.type])
  }

  private interceptWindow(): void {
    window.addEventListener('error', this.onError)
    window.addEventListener('unhandledrejection', this.onUnhandledRejection)
  }

  private interceptConsole(): void {
    console.log = (...args: any[]) => {
      this.originalConsole.log(...args)
      this.publishMessage(LogLevel.INFO, args)
    }

    console.info = (...args: any[]) => {
      this.originalConsole.info(...args)
      this.publishMessage(LogLevel.INFO, args)
    }

    console.warn = (...args: any[]) => {
      this.originalConsole.warn(...args)
      this.publishMessage(LogLevel.WARNING, args)
    }

    console.error = (...args: any[]) => {
      this.originalConsole.error(...args)
      this.publishMessage(LogLevel.ERROR, args)
    }

    console.debug = (...args: any[]) => {
      this.originalConsole.debug(...args)
      this.publishMessage(LogLevel.DEBUG, args)
    }
  }

  private publishMessage(level: LogLevel, args: any[], file?: string, line?: number): void {
    if (!this.session) {
      return
    }

    try {
      const now = new Date()
      const timestamp = {
        sec: Math.floor(now.getTime() / 1000),
        nsec: now.getTime() % 1000 * 1000000,
      }

      if (file === undefined || line === undefined) {
        const { file: errorFile, line: errorLine } = ConsoleLogger.extractErrorLocation(args)
        file = errorFile
        line = errorLine
      }

      const message: Log = {
        timestamp,
        level,
        message: args.map((arg) => ConsoleLogger.stringifyArgument(arg)).join(' '),
        name: frontend.frontend_id,
        file: file ?? '',
        line: line ?? 0,
      }

      const topic = `frontend/${frontend.frontend_id}/logs`
      const payload = JSON.stringify(message)

      this.session.put(topic, payload, { encoding: ConsoleLogger.LOG_ENCODING })
    } catch (error) {
      this.originalConsole.error('[ConsoleLogger] Failed to publish message:', error)
    }
  }

  private static extractErrorLocation(args: any[]): { file: string | undefined; line: number | undefined } {
    for (const arg of args) {
      try {
        if (arg instanceof Error && typeof arg.stack === 'string') {
          const lines = arg.stack.split('\n')
          for (const l of lines) {
            const match = ConsoleLogger.STACK_LINE_REGEX.exec(l)
            if (match) {
              return {
                file: match[1],
                line: parseInt(match[2], 10),
              }
            }
          }
        }
      } catch {
        continue
      }
    }

    return { file: undefined, line: undefined }
  }

  private static stringifyArgument(arg: any): string {
    if (arg === null) {
      return 'null'
    }
    if (arg === undefined) {
      return 'undefined'
    }

    if (arg instanceof Error) {
      return `${arg.name}: ${arg.message}`
    }

    switch (typeof arg) {
      case 'string':
        return arg
      case 'boolean':
      case 'number':
        return String(arg)
      case 'bigint':
        return `${arg}n`
      case 'object':
        try {
          return JSON.stringify(arg)
        } catch {
          return '[Object]'
        }
      case 'function':
        return '[Function]'
      default:
        try {
          return String(arg)
        } catch {
          return '[Unknown]'
        }
    }
  }

  async cleanup(): Promise<void> {
    console.log = this.originalConsole.log
    console.info = this.originalConsole.info
    console.warn = this.originalConsole.warn
    console.error = this.originalConsole.error
    console.debug = this.originalConsole.debug

    window.removeEventListener('error', this.onError)
    window.removeEventListener('unhandledrejection', this.onUnhandledRejection)

    if (this.session) {
      await this.session.close()
      this.session = null
    }
  }
}

const consoleLogger = new ConsoleLogger()

export default consoleLogger
