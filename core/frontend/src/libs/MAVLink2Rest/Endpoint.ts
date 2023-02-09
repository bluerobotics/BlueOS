/* eslint-disable  @typescript-eslint/no-explicit-any */
// The library is an interface for MAVLink objects, messages can by of any type

import Listener from './Listener'

export default class Endpoint {
  socket: WebSocket

  listeners: Array<Listener> = []

  latestData: any = null

  constructor(url: string) {
    this.socket = this.createSocket(url)
  }

  /**
   * Update Endpoint url
   * @param  {string} url
   */
  updateUrl(url: string): void {
    this.socket.close()
    this.socket = this.createSocket(url)
  }

  /**
   * Create websocket for desired URL
   * @param  {string} url
   * @returns WebSocket
   */
  createSocket(url: string): WebSocket {
    const socket = new WebSocket(url)
    socket.onmessage = (message: MessageEvent): void => {
      this.latestData = JSON.parse(message.data)
      for (const listener of this.listeners) {
        listener.onNewData(this.latestData)
      }
    }
    socket.onclose = () => {
      setTimeout(() => {
        this.socket = this.createSocket(url)
      }, 5000)
    }
    return socket
  }

  /**
   * Return a new listener for Endpoint
   */
  addListener(): Listener {
    const newListener = new Listener(this)
    this.listeners.push(newListener)
    return newListener
  }

  /**
   * Remove sired listener from Endpoint
   * @param  {Listener} listener
   */
  removeListener(listener: Listener): void {
    this.listeners = this.listeners.filter((item) => item !== listener)
  }
}
