import { ChannelReceiver, Config, QueryTarget, Reply, Sample, Session, Subscriber } from '@eclipse-zenoh/zenoh-ts'

// zenoh-ts 1.9 no longer exports Receiver/RecvErr; the get() channel rejects receive() on close
// (and the query has its own timeout), so we just map that rejection to Disconnected.
export enum RecvErr {
  Disconnected,
}

export type Receiver = ChannelReceiver<Reply>

export async function receiveQueryReply(receiver: Receiver): Promise<Reply | RecvErr> {
  try {
    return await receiver.receive()
  } catch {
    return RecvErr.Disconnected
  }
}

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

  public async query(key: string, target: QueryTarget, timeout: number = 30000) : Promise<any | null> {
    const session = await this.getSession()
    if (!session) {
      console.error('Zenoh session not initialized')
      return null
    }

    const receiver = await session.get(key, {
      target,
    })

    if (!receiver) {
      console.error('Failed to create query receiver. No queryable found or connection error.')
      return null
    }

    const timeoutPromise = new Promise<null>((resolve) => {
      setTimeout(() => resolve(null), timeout)
    })

    const replyPromise = receiveQueryReply(receiver)
    const reply = await Promise.race([replyPromise, timeoutPromise])

    if (reply === null || reply === RecvErr.Disconnected) {
      console.error('Query timeout: No response from zenoh queryable. '
        + 'The service may be unavailable or the extension may not exist.')
      return null
    }

    if (!reply || typeof (reply as any).result !== 'function') {
      console.error('Unexpected reply from zenoh queryable:', reply)
      return null
    }

    const payload = (reply as { result: () => Sample }).result()
    try {
      return JSON.parse(payload.payload().toString())
    } catch (error) {
      console.error('Error parsing response:', error)
      return null
    }
  }

  public async subscriber(topic: string, handler: (sample: Sample) => Promise<void>) : Promise<Subscriber | null> {
    const session = await this.getSession()
    if (!session) {
      console.error('Zenoh session not initialized')
      return null
    }

    return session.declareSubscriber(topic, {
      handler,
    })
  }
}

const zenoh = ZenohManager.getInstance()

export default zenoh
