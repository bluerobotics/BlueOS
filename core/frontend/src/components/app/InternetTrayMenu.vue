<template>
  <v-menu
    v-model="show_menu"
    :close-on-content-click="false"
    nudge-left="275"
    nudge-bottom="25"
    :disabled="!settings.is_pirate_mode"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        class="px-1"
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
          v-tooltip="tooltip"
          color="white"
        >
          {{ icon }}
        </v-icon>
      </v-card>
    </template>
    <v-dialog
      v-model="show_menu"
      width="fit-content"
      max-width="80%"
    >
      <network-interface-menu
        v-if="show_menu"
        :initial-page="dns_failure ? 'dns_configuration' : ''"
        @close="show_menu = false"
      />
    </v-dialog>
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'
import helper from '@/store/helper'
import { InternetConnectionState } from '@/types/helper'

import NetworkInterfaceMenu from './NetworkInterfaceMenu.vue'

export default Vue.extend({
  name: 'InternetTrayMenu',
  components: {
    NetworkInterfaceMenu,
  },
  data: () => ({
    settings,
    show_menu: false,
  }),
  computed: {
    dns_failure(): boolean {
      return helper.dns_failure
    },
    tooltip() {
      if (this.dns_failure) {
        return 'Internet is reachable by IP, but DNS name resolution is failing. Check DNS nameservers.'
      }
      switch (helper.has_internet) {
        case InternetConnectionState.ONLINE:
          return 'Vehicle has internet access.'
        case InternetConnectionState.OFFLINE:
          return 'Internet connection is not available.'
        case InternetConnectionState.LIMITED:
          return 'Internet connection is limited.'
        case InternetConnectionState.UNKNOWN:
          return 'Internet connection status is unknown.'
        default:
          return 'Internet connection is not available.'
      }
    },
    icon(): string {
      if (this.dns_failure) {
        return 'mdi-dns'
      }
      switch (helper.has_internet) {
        case InternetConnectionState.ONLINE:
          return 'mdi-web'
        case InternetConnectionState.OFFLINE:
          return 'mdi-web-off'
        case InternetConnectionState.LIMITED:
          return 'mdi-web-minus'
        case InternetConnectionState.UNKNOWN:
          return 'mdi-web-refresh'
        default:
          return 'mdi-web-off'
      }
    },
  },
})
</script>
