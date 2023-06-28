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
          color="white"
          :title="tooltip"
        >
          {{ helper.has_internet ? 'mdi-web' : 'mdi-web-off' }}
        </v-icon>
      </v-card>
    </template>
    <v-dialog
      v-model="show_menu"
      width="fit-content"
      max-width="80%"
    >
      <network-interface-priority-menu
        v-if="show_menu"
        @close="show_menu = false"
      />
    </v-dialog>
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'
import helper from '@/store/helper'

import NetworkInterfacePriorityMenu from './NetworkInterfacePriorityMenu.vue'

export default Vue.extend({
  name: 'InternetTrayMenu',
  components: {
    NetworkInterfacePriorityMenu,
  },
  data: () => ({
    helper,
    settings,
    show_menu: false,
  }),
  computed: {
    tooltip() {
      return helper.has_internet ? 'Vehicle has internet access.' : 'Internet connection is not available.'
    },
  },
})
</script>
