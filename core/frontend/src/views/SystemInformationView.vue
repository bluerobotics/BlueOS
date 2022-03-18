<template>
  <v-container
    style="max-width:90%"
  >
    <v-row
      no-gutters
    >
      <v-col
        md="3"
      >
        <v-card
          elevation="2"
          class="ma-3"
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
                v-for="item in items"
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
      </v-col>

      <v-col
        v-if="true"
        md="9"
      >
        <processes v-if="page_selected == 'process'" />
        <system-condition v-if="page_selected == 'system_condition'" />
        <network v-if="page_selected == 'network'" />
        <about-this-system v-if="page_selected == 'about'" />
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import AboutThisSystem from '@/components/system-information/AboutThisSystem.vue'
import Network from '@/components/system-information/Network.vue'
import Processes from '@/components/system-information/Processes.vue'
import SystemCondition from '@/components/system-information/SystemCondition.vue'

export default Vue.extend({
  name: 'SystemInformationView',
  components: {
    AboutThisSystem,
    Network,
    Processes,
    SystemCondition,
  },
  data() {
    return {
      items: [
        { title: 'Processes', icon: 'mdi-view-dashboard', value: 'process' },
        { title: 'System Condition', icon: 'mdi-speedometer', value: 'system_condition' },
        { title: 'Network', icon: 'mdi-ip-network-outline', value: 'network' },
        { title: 'About', icon: 'mdi-information', value: 'about' },
      ],
      page_selected: 'process',
    }
  },
})
</script>
