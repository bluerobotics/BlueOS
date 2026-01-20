<template>
  <v-card
    height="100%"
  >
    <v-tabs
      v-model="page_selected"
      centered
      icons-and-text
      show-arrows
    >
      <v-tabs-slider />
      <v-tab
        v-for="page in pages"
        :key="page.value"
      >
        {{ page.title }}
        <v-icon>{{ page.icon }}</v-icon>
      </v-tab>
    </v-tabs>
    <v-tabs-items v-model="page_selected">
      <v-tab-item
        v-for="page in pages"
        :key="page.value"
      >
        <processes v-if="page.value === 'process'" />
        <system-condition v-else-if="page.value === 'system_condition'" />
        <network v-else-if="page.value === 'network'" />
        <usb v-else-if="page.value === 'usb'" />
        <kernel v-else-if="page.value === 'kernel'" />
        <journal v-else-if="page.value === 'journal'" />
        <firmware v-else-if="page.value === 'firmware'" />
        <about-this-system v-else-if="page.value === 'about'" />
      </v-tab-item>
    </v-tabs-items>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import AboutThisSystem from '@/components/system-information/AboutThisSystem.vue'
import Firmware from '@/components/system-information/Firmware.vue'
import Journal from '@/components/system-information/Journal.vue'
import Kernel from '@/components/system-information/Kernel.vue'
import Network from '@/components/system-information/Network.vue'
import Processes from '@/components/system-information/Processes.vue'
import SystemCondition from '@/components/system-information/SystemCondition.vue'
import Usb from '@/components/system-information/Usb.vue'
import settings from '@/libs/settings'

export interface Item {
  title: string,
  icon: string,
  value: string,
  is_pirate?: boolean,
}

export default Vue.extend({
  name: 'SystemInformationView',
  components: {
    AboutThisSystem,
    Firmware,
    Journal,
    Kernel,
    Network,
    Processes,
    SystemCondition,
    Usb,
  },
  data() {
    return {
      settings,
      items: [
        { title: 'System Monitor', icon: 'mdi-speedometer', value: 'system_condition' },
        { title: 'Processes', icon: 'mdi-view-dashboard', value: 'process' },
        { title: 'Network', icon: 'mdi-ip-network-outline', value: 'network' },
        { title: 'USB', icon: 'mdi-usb', value: 'usb' },
        {
          title: 'Kernel', icon: 'mdi-text-long', value: 'kernel', is_pirate: true,
        },
        {
          title: 'Journal', icon: 'mdi-notebook-outline', value: 'journal', is_pirate: true,
        },
        {
          title: 'Firmware', icon: 'mdi-raspberry-pi', value: 'firmware', is_pirate: true,
        },
        { title: 'About', icon: 'mdi-information', value: 'about' },
      ] as Item[],
      page_selected: null as string | null,
    }
  },
  computed: {
    pages(): Item[] {
      return this.items
        .filter((item: Item) => item?.is_pirate !== true || this.settings.is_pirate_mode)
    },
  },
})
</script>
