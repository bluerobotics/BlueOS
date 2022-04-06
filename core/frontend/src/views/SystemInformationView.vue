<template>
  <v-container
    style="max-width:90%"
    class="d-flex my-6"
  >
    <v-card
      elevation="2"
      class="mr-4"
    >
      <v-navigation-drawer
        floating
        permanent
      >
        <v-list
          dense
          rounded
        >
          <v-list-item
            v-for="item in pages"
            :key="item.title"
            link
            :input-value="item.value == page_selected"
            @click="page_selected=item.value"
          >
            <v-list-item-icon>
              <v-icon>{{ item.icon }}</v-icon>
            </v-list-item-icon>

            <v-list-item-content>
              <v-list-item-title>{{ item.title }}</v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list>
      </v-navigation-drawer>
    </v-card>

    <v-card
      elevation="2"
      width="100%"
    >
      <processes v-if="page_selected == 'process'" />
      <system-condition v-if="page_selected == 'system_condition'" />
      <network v-if="page_selected == 'network'" />
      <kernel v-if="page_selected == 'kernel'" />
      <about-this-system v-if="page_selected == 'about'" />
    </v-card>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import AboutThisSystem from '@/components/system-information/AboutThisSystem.vue'
import Kernel from '@/components/system-information/Kernel.vue'
import Network from '@/components/system-information/Network.vue'
import Processes from '@/components/system-information/Processes.vue'
import SystemCondition from '@/components/system-information/SystemCondition.vue'
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
    Kernel,
    Network,
    Processes,
    SystemCondition,
  },
  data() {
    return {
      settings,
      items: [
        { title: 'Processes', icon: 'mdi-view-dashboard', value: 'process' },
        { title: 'System Monitor', icon: 'mdi-speedometer', value: 'system_condition' },
        { title: 'Network', icon: 'mdi-ip-network-outline', value: 'network' },
        {
          title: 'Kernel', icon: 'mdi-text-subject', value: 'kernel', is_pirate: true,
        },
        { title: 'About', icon: 'mdi-information', value: 'about' },
      ] as Item[],
      page_selected: 'process',
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
