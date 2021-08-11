/* eslint-disable  @typescript-eslint/no-explicit-any */
// The library is an interface for MAVLink objects, messages can by of any type

import Endpoint from './Endpoint'
import Listener from './Listener'

interface Dictionary<T> {
  [key: string]: T;
}

class Mavlink2RestManager {
  baseUrl: string;

  // Dictionary mapping endpoints to websocket
  endpoints: Dictionary<Endpoint> = {}

  baseUrlCandidates: Array<string>

  private static instance: Mavlink2RestManager;

  private constructor() {
    this.baseUrl = `${Mavlink2RestManager.getWebsocketPrefix()}://${window.location.host}/mavlink2rest/ws/mavlink`
    this.baseUrlCandidates = [this.baseUrl, 'ws://localhost:8088/ws/mavlink']
    this.probeBaseUrlCandidates()
  }

  /**
   * Singleton access
   * @returns Mavlink2RestManager
   */
  public static getInstance(): Mavlink2RestManager {
    if (!Mavlink2RestManager.instance) {
      Mavlink2RestManager.instance = new Mavlink2RestManager()
    }
    return Mavlink2RestManager.instance
  }

  /**
   * Check for valid base URL from REST API
   */
  probeBaseUrlCandidates(): void {
    this.baseUrlCandidates.forEach((url) => {
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
    })
  }

  /**
   * Force base URL for REST API
   * @param  {string} url
   */
  setBaseUrl(url: string): void {
    // close all websockets and discard them
    Object.entries(this.endpoints).forEach(([name, endpoint]) => {
      endpoint.updateUrl(`${url}?filter=${name}`)
    })
  }

  /**
   * Create Listener based in endpoint name
   * @param  {string} endpointName
   * @returns Listener
   */
  startListening(endpointName: string): Listener {
    const endpoint = this.endpoints[endpointName] || this.createEndpoint(endpointName)
    this.endpoints[endpointName] = endpoint
    return endpoint.addListener()
  }

  /**
   * Create endpoint based in MAVLink message name
   * @param  {string} endpoint
   * @returns Endpoint
   */
  createEndpoint(messageName: string): Endpoint {
    return new Endpoint(`${this.baseUrl}?filter=${messageName}`)
  }

  /**
   * Check for valid mavlink websocket prefix
   */
  public static getWebsocketPrefix(): string {
    return window.location.protocol === 'https:' ? 'wss' : 'ws'
  }
}

// Define public instance of singleton
const mavlink2rest = Mavlink2RestManager.getInstance()

export default mavlink2rest
