import Vue from 'vue'
import {
  Action, getModule, Mutation, VuexModule,
} from 'vuex-module-decorators'

import mavlink2rest from '@/libs/MAVLink2Rest'
import Listener from '@/libs/MAVLink2Rest/Listener'
import store from '@/store'
import { Dictionary } from '@/types/common'
import { MavlinkMessage } from '@/types/mavlink'

import autopilot_data from './autopilot'

interface messsageRefreshRate {
  messageName: string
  refreshRate: number
}

// Per-message requested rates from live consumers; wire rate is max(claims), or 1 Hz when empty.
const message_rate_claims: Dictionary<number[]> = {}
const IDLE_MESSAGE_RATE_HZ = 1

function claimedRefreshRate(messageName: string): number {
  const claims = message_rate_claims[messageName]
  if (!claims?.length) {
    return IDLE_MESSAGE_RATE_HZ
  }
  return Math.max(...claims)
}

@Module({
  dynamic: true,
  store,
  name: 'mavlink',
})

class MavlinkStore extends VuexModule {
  available_messages: Dictionary<MavlinkMessage> = {}

  available_identified_messages: Dictionary<Dictionary<MavlinkMessage>> = {}

  message_listeners: Dictionary<Listener> = {}

  @Action
  subscribeMessageRefreshRate(rate: messsageRefreshRate): void {
    const { messageName, refreshRate } = rate
    if (refreshRate < 0) {
      console.warn(`Invalid request rate requested for message ${messageName}@${refreshRate}Hz`)
      return
    }

    if (!message_rate_claims[messageName]) {
      message_rate_claims[messageName] = []
    }
    message_rate_claims[messageName].push(refreshRate)
    this.applyMessageRefreshRate(messageName)
  }

  @Action
  unsubscribeMessageRefreshRate(rate: messsageRefreshRate): void {
    const { messageName, refreshRate } = rate
    const claims = message_rate_claims[messageName]
    if (!claims?.length) {
      return
    }

    const index = claims.indexOf(refreshRate)
    if (index < 0) {
      console.warn(`No ${refreshRate}Hz claim to release for message ${messageName}`)
      return
    }
    claims.splice(index, 1)
    this.applyMessageRefreshRate(messageName)
  }

  /** Lifetime / one-shot claim. Prefer subscribe/unsubscribe when the consumer leaves. */
  @Action
  setMessageRefreshRate(rate: messsageRefreshRate): void {
    this.subscribeMessageRefreshRate(rate)
  }

  @Action
  applyMessageRefreshRate(messageName: string): void {
    const refreshRate = claimedRefreshRate(messageName)

    // Equal rate: keep existing listener and skip the wire request.
    // Any other rate change discards the listener and creates a replacement.
    if (messageName in this.message_listeners) {
      if (this.message_listeners[messageName].frequency === refreshRate) {
        return
      }
      this.message_listeners[messageName].discard()
    }

    mavlink2rest.requestMessageRate(messageName, refreshRate, autopilot_data.system_id)

    this.message_listeners[messageName] = mavlink2rest.startListening(messageName).setCallback((receivedMessage) => {
      this.updateMessage({
        messageName,
        messageData: receivedMessage,
        requestedMessageRate: refreshRate,
        timestamp: new Date(),
      })
    }).setFrequency(refreshRate)
  }

  @Mutation
  updateMessage(message: MavlinkMessage): void {
    if (message) {
      // TODO: Check if this is the best possible way to update `available_messages`
      // Reference: https://github.com/bluerobotics/BlueOS/pull/508#discussion_r718729077
      // We should not use `message.messageName` as dictionary key since it's a regex,
      // the best approach is to use the message name as key
      const messageName = (message.messageData.message as any).type
      const { header } = message.messageData
      const identifier = `${header.system_id}_${header.component_id}`
      Vue.set(this.available_messages, messageName, message)
      // make sure identifier exists
      if (!(identifier in this.available_identified_messages)) {
        Vue.set(this.available_identified_messages, identifier, {})
      }
      Vue.set(this.available_identified_messages[identifier], messageName, message)
    }
  }
}

export { MavlinkStore }

const mavlink: MavlinkStore = getModule(MavlinkStore)
export default mavlink
