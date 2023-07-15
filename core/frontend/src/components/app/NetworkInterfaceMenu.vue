<template>
  <v-card>
    <v-container fluid>
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
          <network-interface-priority-menu v-if="page.value === 'network_interface_priority'" @close="close" />
          <dns-configuration-menu v-else-if="page.value === 'dns_configuration'" @close="close" />
        </v-tab-item>
      </v-tabs-items>
    </v-container>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import DnsConfigurationMenu from '@/components/app/DnsConfigurationMenu.vue'
import NetworkInterfacePriorityMenu from '@/components/app/NetworkInterfacePriorityMenu.vue'

export interface Item {
  title: string,
  icon: string,
  value: string,
}

export default Vue.extend({
  name: 'NetworkInterfaceMenu',
  components: {
    NetworkInterfacePriorityMenu,
    DnsConfigurationMenu,
  },
  data() {
    return {
      page_selected: null as string | null,
      pages: [
        { title: 'Network Interface Priority', icon: 'mdi-sort', value: 'network_interface_priority' },
        { title: 'Dns Configuration', icon: 'mdi-dns', value: 'dns_configuration' },
      ] as Item[],
    }
  },
  methods: {
    close() {
      this.$emit('close')
    },
  },
})
</script>
