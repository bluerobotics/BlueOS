/* eslint-disable  @typescript-eslint/no-explicit-any */
// The library is an interface for MAVLink objects, messages can by of any type

import type Endpoint from './Endpoint'

export default class Listener {
  // eslint-disable-next-line class-methods-use-this
  callback: (msg: any) => void = () => { console.log('Listener not assigned a callback') }

  parent: Endpoint

  frequency = 1

  interval = -1

  constructor(parent: Endpoint) {
    this.parent = parent
    this.setFrequency(1)
  }

  /**
   * Define callback to be used when a new message is available
   * @param  {(msg:any)=>void} callback
   * @returns Listener
   */
  setCallback(callback: (msg: any) => void): Listener {
    this.callback = callback
    return this
  }

  /**
   * Set desired frequency for the callback
   * @param  {number} frequency
   * @returns Listener
   */
  setFrequency(frequency: number): Listener {
    clearInterval(this.interval)
    this.frequency = frequency
    if (frequency === 0) {
      return this
    }
    this.interval = window.setInterval(() => {
      if (this.parent.latestData !== null) {
        this.callback(this.parent.latestData)
      }
    }, 1000 / frequency)
    return this
  }

  /**
   * If frequency is set to zero, consume data as soon as received
   */
  onNewData(data: any): void {
    if (this.frequency === 0) {
      this.callback(data)
    }
  }

  discard(): void {
    clearInterval(this.interval)
    this.parent.removeListener(this)
  }
}
