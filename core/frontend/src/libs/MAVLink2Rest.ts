/* eslint-disable  @typescript-eslint/no-explicit-any */
// The library is an interface for MAVLink objects, messages can by of any type

interface Dictionary<T> {
  [key: string]: T;
}

class Listener {
  callback: (msg: any) => void = () => { console.log('Listener not assigned a callback') };
  parent: Endpoint;
  frequency = 1
  interval = -1;

  constructor (parent: Endpoint) {
    this.parent = parent
    this.setFrequency(1)
  }

  /**
   * Define callback to be used when a new message is available
   * @param  {(msg:any)=>void} callback
   * @returns Listener
   */
  setCallback (callback: (msg: any) => void): Listener {
    this.callback = callback
    return this
  }

  /**
   * Set desired frequency for the callback
   * @param  {number} frequency
   * @returns Listener
   */
  setFrequency (frequency: number): Listener {
    clearInterval(this.interval)
    this.interval = window.setInterval(() => {
      if (this.parent.latestData !== null) {
        this.callback(this.parent.latestData)
      }
    }, 1000 / frequency)
    return this
  }

  discard () {
    clearInterval(this.interval)
    this.parent.removeListener(this)
  }
}

class Endpoint {
  socket: WebSocket;
  listeners: Array<Listener> = [];
  latestData: any = null;

  constructor (url: string) {
    this.socket = this.createSocket(url)
  }

  /**
   * Update Endpoint url
   * @param  {string} url
   */
  updateUrl (url: string) {
    this.socket.close()
    this.socket = this.createSocket(url)
  }

  /**
   * Create websocket for desired URL
   * @param  {string} url
   * @returns WebSocket
   */
  createSocket (url: string): WebSocket {
    const socket = new WebSocket(url)
    socket.onmessage = (message: MessageEvent) => {
      this.latestData = JSON.parse(message.data)
    }
    return socket
  }

  /**
   * Return a new listener for Endpoint
   */
  addListener () {
    const newListener = new Listener(this)
    this.listeners.push(newListener)
    return newListener
  }

  /**
   * Remove sired listener from Endpoint
   * @param  {Listener} listener
   */
  removeListener (listener: Listener) {
    this.listeners = this.listeners.filter((item) => item !== listener)
  }
}

class Mavlink2RestManager {
  baseUrl: string;
  // Dictionary mapping endpoints to websocket
  endpoints: Dictionary<Endpoint> = {}
  baseUrlCandidates: Array<string>

  private static instance: Mavlink2RestManager;

  private constructor () {
    this.baseUrl = `${this.getWebsocketPrefix()}://${window.location.host}/mavlink2rest/ws/mavlink`
    this.baseUrlCandidates = [this.baseUrl, 'ws://localhost:8088/ws/mavlink']
    this.probeBaseUrlCandidates()
  }

  /**
   * Singleton access
   * @returns Mavlink2RestManager
   */
  public static getInstance (): Mavlink2RestManager {
    if (!Mavlink2RestManager.instance) {
      Mavlink2RestManager.instance = new Mavlink2RestManager()
    }
    return Mavlink2RestManager.instance
  }

  /**
   * Check for valid base URL from REST API
   */
  probeBaseUrlCandidates () {
    for (const url of this.baseUrlCandidates) {
      const asHttp = url.replace('wss://', 'https://').replace('ws://', 'http://').replace('/ws/mavlink', '')
      fetch(asHttp)
        .then(async (res) => {
          if (res.status === 200) {
            const body = await res.text()
            const valid = body.indexOf('List of available paths') !== -1
            if (valid) {
              this.setBaseUrl(url)
            }
          }
        })
    }
  }

  /**
   * Force base URL for REST API
   * @param  {string} url
   */
  setBaseUrl (url: string) {
    // close all websockets and discard them
    for (const [name, endpoint] of Object.entries(this.endpoints)) {
      endpoint.updateUrl(`${url}?filter=${name}`)
    }
  }

  /**
   * Create Listener based in endpoint name
   * @param  {string} endpointName
   * @returns Listener
   */
  startListening (endpointName: string): Listener {
    const endpoint = this.endpoints[endpointName] || this.createEndpoint(endpointName)
    this.endpoints[endpointName] = endpoint
    return endpoint.addListener()
  }

  /**
   * Create endpoint based in MAVLink message name
   * @param  {string} endpoint
   * @returns Endpoint
   */
  createEndpoint (messageName: string): Endpoint {
    return new Endpoint(`${this.baseUrl}?filter=${messageName}`)
  }

  /**
   * Check for valid mavlink websocket prefix
   */
  getWebsocketPrefix () {
    return window.location.protocol == 'https:' ? 'wss' : 'ws'
  }

}

// Define public instance of singleton
const mavlink2rest = Mavlink2RestManager.getInstance()

export default mavlink2rest