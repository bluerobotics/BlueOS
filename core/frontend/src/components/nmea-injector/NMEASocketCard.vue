<template>
  <v-card
    width="100%"
    class="pa-0 my-4"
  >
    <v-card-text class="pa-4">
      <v-container class="pa-0">
        <v-card class="elevation-0 pa-0">
          <v-card-text
            class="d-flex align-center pa-0 justify-center"
          >
            <span class="text-subtitle-1 mr-2">
              {{ nmeaSocket.kind }}:{{ nmeaSocket.port }}
            </span>
            <v-icon>mdi-arrow-right-circle</v-icon>
            <span class="text-subtitle-1 ml-2">
              Mavlink Component #{{ nmeaSocket.component_id }}
            </span>
          </v-card-text>
        </v-card>
      </v-container>
      <v-fab-transition>
        <v-btn
          color="error"
          fab
          dark
          small
          absolute
          bottom
          right
          @click="removeNMEASocket"
        >
          <v-icon>mdi-minus</v-icon>
        </v-btn>
      </v-fab-transition>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import Notifier from '@/libs/notifier'
import nmea_injector from '@/store/nmea-injector'
import { nmea_injector_service } from '@/types/frontend_services'
import { NMEASocket } from '@/types/nmea-injector'
import back_axios from '@/utils/api'

const notifier = new Notifier(nmea_injector_service)

export default Vue.extend({
  name: 'NMEASocketCard',
  props: {
    nmeaSocket: {
      type: Object as PropType<NMEASocket>,
      required: true,
    },
  },
  methods: {
    async removeNMEASocket(): Promise<void> {
      nmea_injector.setUpdatingNMEASockets(true)
      await back_axios({
        method: 'delete',
        url: `${nmea_injector.API_URL}/socks`,
        timeout: 10000,
        data: this.nmeaSocket,
      })
        .catch((error) => {
          notifier.pushBackError('nmeaSocket_DELETE_FAIL', error)
        })
    },
  },
})
</script>
