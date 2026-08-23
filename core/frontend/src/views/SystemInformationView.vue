<template>
  <v-card
    height="100%"
  >
    <v-tabs
      v-model="current_page"
      centered
      icons-and-text
      show-arrows
    >
      <v-tabs-slider />
      <v-tab
        v-for="page in pages"
        :key="page.value"
        :tab-value="page.value"
      >
        {{ page.title }}
        <v-icon>{{ page.icon }}</v-icon>
      </v-tab>
    </v-tabs>
    <!-- Only mount the active tab so heavy consumers (kernel/journal WS) tear down when leaving -->
    <processes v-if="current_page === 'process'" />
    <system-condition v-else-if="current_page === 'system_condition'" />
    <network v-else-if="current_page === 'network'" />
    <usb v-else-if="current_page === 'usb'" />
    <kernel v-else-if="current_page === 'kernel'" />
    <journal v-else-if="current_page === 'journal'" />
    <firmware v-else-if="current_page === 'firmware'" />
    <about-this-system v-else-if="current_page === 'about'" />
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
      page_value: 'system_condition',
    }
  },
  computed: {
    pages(): Item[] {
      return this.items
        .filter((item: Item) => item?.is_pirate !== true || this.settings.is_pirate_mode)
    },
    current_page: {
      get(): string {
        return this.pages.find((page) => page.value === this.page_value)?.value
          ?? this.pages[0].value
      },
      set(value: string) {
        this.page_value = value
      },
    },
  },
})
</script>
