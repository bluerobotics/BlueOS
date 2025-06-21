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
        <zenoh-inspector v-if="page.value === 'topics'" />
        <zenoh-network v-else-if="page.value === 'network'" />
      </v-tab-item>
    </v-tabs-items>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import ZenohInspector from '@/components/zenoh-inspector/ZenohInspector.vue'
import ZenohNetwork from '@/components/zenoh-inspector/ZenohNetwork.vue'

export interface Item {
  title: string,
  icon: string,
  value: string,
}

export default Vue.extend({
  name: 'ZenohInspectorView',
  components: {
    'zenoh-inspector': ZenohInspector,
    'zenoh-network': ZenohNetwork,
  },
  data() {
    return {
      items: [
        { title: 'Topics', icon: 'mdi-message-text', value: 'topics' },
        { title: 'Network', icon: 'mdi-lan', value: 'network' },
      ] as Item[],
      page_selected: 'topics',
    }
  },
  computed: {
    pages(): Item[] {
      return this.items
    },
  },
})
</script>
