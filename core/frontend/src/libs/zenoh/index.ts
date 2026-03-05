import { Config, Session } from '@eclipse-zenoh/zenoh-ts'

class ZenohManager {
  private static instance: ZenohManager

  private sessionPromise: Promise<Session> | null = null

  private constructor() {}

  public static getInstance(): ZenohManager {
    if (!ZenohManager.instance) {
      ZenohManager.instance = new ZenohManager()
    }
    return ZenohManager.instance
  }

  public static getWebsocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${window.location.host}/zenoh-api/`
  }

  public getSession(): Promise<Session> {
    if (!this.sessionPromise) {
      const url = ZenohManager.getWebsocketUrl()
      const config = new Config(url)
      this.sessionPromise = Session.open(config).catch((err) => {
        this.sessionPromise = null
        throw err
      })
    }
    return this.sessionPromise
  }
}

const zenoh = ZenohManager.getInstance()

export default zenoh
