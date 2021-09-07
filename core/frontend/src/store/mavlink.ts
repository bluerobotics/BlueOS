import Vue from 'vue'
import {
  Action, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import mavlink2rest from '@/libs/MAVLink2Rest'
import Listener from '@/libs/MAVLink2Rest/Listener'
import store from '@/store'
import { Dictionary } from '@/types/common'
import { MavlinkMessage } from '@/types/mavlink'

interface messsageRefreshRate {
  message: string
  refreshRate: number
}

@Module({
  dynamic: true,
  store,
  name: 'mavlink_store',
})

export default class MavlinkStore extends VuexModule {
  available_messages: Dictionary<MavlinkMessage> = {}

  message_listeners: Dictionary<Listener> = {}

  @Action({ commit: 'updateMessage' })
  setMessageRefreshRate(rate: messsageRefreshRate): void {
    const messageName = rate.message
    const { refreshRate } = rate
    if (refreshRate < 0) {
      console.warn(`invalid request rate requested for message ${messageName} : ${rate} Hz`)
    }

    mavlink2rest.requestMessageRate(messageName, refreshRate)
    // remove any listener we currently have set
    // Should we only replace it if someone requests a higher messageRate?
    if (this.message_listeners[messageName]) {
      this.message_listeners[messageName].discard()
    }
    // create a new listener
    this.message_listeners[messageName] = mavlink2rest.startListening(messageName).setCallback((receivedMessage) => {
      this.updateMessage({
        messageName,
        messageData: receivedMessage,
        requestedMessageRate: refreshRate,
      })
    }).setFrequency(refreshRate)
  }

  @Mutation
  updateMessage(message: MavlinkMessage): void {
    if (message) {
      Vue.set(this.available_messages, message.messageName, message)
    }
  }
}
