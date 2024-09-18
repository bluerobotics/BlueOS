<template>
  <v-card
    height="100%"
  >
    <not-safe-overlay />
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
        <network-speed-test v-if="page.value === 'network-speed-test'" />
        <internet-speed-test v-else-if="page.value === 'internet-speed-test'" />
      </v-tab-item>
    </v-tabs-items>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import NotSafeOverlay from '@/components/common/NotSafeOverlay.vue'
import InternetSpeedTest from '@/components/speedtest/InternetSpeedTest.vue'
import NetworkSpeedTest from '@/components/speedtest/NetworkSpeedTest.vue'

export interface Item {
  title: string,
  icon: string,
  value: string,
}

export default Vue.extend({
  name: 'NetworkTestView',
  components: {
    InternetSpeedTest,
    NetworkSpeedTest,
    NotSafeOverlay,
  },
  data() {
    return {
      pages: [
        { title: 'Local network test', icon: 'mdi-speedometer', value: 'network-speed-test' },
        { title: 'Internet speed test', icon: 'mdi-web', value: 'internet-speed-test' },
      ] as Item[],
      page_selected: null as string | null,
    }
  },
})
</script>
