/* eslint-disable  @typescript-eslint/no-explicit-any */
// The library is an interface for MAVLink objects, messages can by of any type

import axios from 'axios'

import { Dictionary } from '@/types/common'

import Endpoint from './Endpoint'
import Listener from './Listener'
import messageId from './MessageID'
import autopilot_data from '@/store/autopilot'
import { MAVLinkType, MavCmd } from './mavlink2rest-ts/messages/mavlink2rest-enum'

class Mavlink2RestManager {
  baseUrl: string

  // Dictionary mapping endpoints to websocket
  endpoints: Dictionary<Endpoint> = {}

  baseUrlCandidates: Array<string>

  private socket: WebSocket | undefined = undefined

  private static instance: Mavlink2RestManager

  private constructor() {
    this.baseUrl = `${Mavlink2RestManager.getWebsocketPrefix()}://${window.location.host}/mavlink2rest/ws/mavlink`
    this.baseUrlCandidates = [
      this.baseUrl,
    ]
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
        .finally(() => {
          if (this.socket === undefined) {
            this.setBaseUrl(this.baseUrl)
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

    this.socket = this.createSocket(`${url}?filter=THIS_SHOULD_ONLY_SEND`)
  }

  /**
   * Create websocket for internal use
   * @param  {string} url
   * @returns WebSocket
   */
  createSocket(url: string): WebSocket {
    const socket = new WebSocket(url)
    socket.onclose = () => {
      setTimeout(() => {
        this.socket = this.createSocket(url)
      }, 5000)
    }
    socket.onerror = (event: Event) => {
      console.debug(`M2R Websocket got an error: ${event.type}`)
    }
    return socket
  }

  /**
   * Helper for COMMAND_LONG messages
   * @param command 
   */

  sendCommandLong(
    command: MavCmd,
    param1: number | undefined = undefined,
    param2: number | undefined = undefined,
    param3: number | undefined = undefined,
    param4: number | undefined = undefined,
    param5: number | undefined = undefined,
    param6: number | undefined = undefined,
    param7: number | undefined = undefined
  ) {
    mavlink2rest.sendMessage({
      header: {
        system_id: 255,
        component_id: 1,
        sequence: 1,
      },
      message: {
        type: MAVLinkType.COMMAND_LONG,
        param1: param1 ?? 0,
        param2: param2 ?? 0,
        param3: param3 ?? 0,
        param4: param4 ?? 0,
        param5: param5 ?? 0,
        param6: param6 ?? 0,
        param7: param7 ?? 0,
        command: {
          type: command,
        },
        target_system: autopilot_data.system_id,
        target_component: 1,
        confirmation: 0,
      },
    })
  }


  waitForAck(command: MavCmd, timeout_seconds: number = 3): Promise<any> {
    return new Promise((resolve, reject) => {
      const listener = this.startListening(MAVLinkType.COMMAND_ACK).setCallback(
        (content) => {
          const { header, message } = content
          if (header.system_id !== autopilot_data.system_id || header.component_id !== 1) {
            return
          }
          if (message.command.type === command) {
            resolve(message)
          }
        }
      ).setFrequency(0)
      setTimeout(() => {
        listener.discard()
        reject(new Error(`timed out waiting for answer for ${command}`))
      }, timeout_seconds*1000)
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
   * Sends a mesage using mavlink2rest with websocket
   * @param  {string} message data
   *
   */
  sendMessageViaWebsocket(message: any): void {
    try {
      this.socket?.send(JSON.stringify(message))
    } catch (error) {
      console.log(`Failed to parse message: ${error}`)
    }
  }

  /**
   * Sends a mesage using mavlink2rest
   * @param  {string} message data
   *
   */
  sendMessage(message: any): void {
    // TODO: Abstract that and use websocket to do the post and deal with the answer somehow
    axios.post(`${this.baseUrl}/mavlink`.replace('/ws/mavlink', '').replace('ws', 'http'), message)
      .catch((error) => console.log(`unable to send message ${message}: ${error}`))
  }

  /**
   * Requests a message at a given rate
   * @param  {string} message name
   * @returns Listener
   */
  requestMessageRate(message: string, rate:number, system_id: number): void {
    if (rate < 0) {
      console.warn(`Requested invalid message rate for ${message}: ${rate}`)
      return
    }
    if (!Object.keys(messageId).includes(message)) {
      console.warn(
        `Requesting for an unmapped message (${message})! Please add it to mavlink2rest/MessageID.ts`,
      )
    }
    const payload = {
      header: {
        system_id: 255,
        component_id: 0,
        sequence: 0,
      },
      message: {
        type: 'COMMAND_LONG',
        param1: messageId[message],
        param2: 1000000 / rate,
        param3: 0.0,
        param4: 0.0,
        param5: 0.0,
        param6: 0.0,
        param7: 0.0,
        command: {
          type: 'MAV_CMD_SET_MESSAGE_INTERVAL',
        },
        target_system: system_id,
        target_component: 0,
        confirmation: 0,
      },
    }
    this.sendMessage(payload)
  }

  /**
   * Abstraction over PARAM_SET message
   * @param {string} name Parameter name
   * @param {number} value Desired parameter value
   * @param {string} type Valid mavlink parameter type based on mavlink2rest
   */
  setParam(name: string, value: number, sysid: number, type?: string): void {
    const param_name = [...name]
    while (param_name.length < 16) {
      param_name.push('\0')
    }

    this.sendMessageViaWebsocket({
      header: {
        system_id: 255,
        component_id: 0,
        sequence: 0,
      },
      message: {
        type: 'PARAM_SET',
        param_value: value,
        target_system: sysid,
        target_component: 0,
        param_id: param_name,
        param_type: {
          type: type ?? 'MAV_PARAM_TYPE_UINT8',
        },
      },
    })
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
