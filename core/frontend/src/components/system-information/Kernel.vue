<template>
  <v-container fluid>
    <v-row>
      <v-col>
        <v-sheet
          min-height="70vh"
          rounded="lg"
        >
          <v-card
            elevation="0"
          >
            <v-virtual-scroll
              :item-height="20"
              :items="messages"
              height="700px"
            >
              <template #default="{ item }">
                <v-list-item>
                  <!--
                    TODO: text-wrap is not possible until https://github.com/vuetifyjs/vuetify/issues/11755 gets fixed
                  -->
                  <v-list-item-title
                    class="pa-0"
                    :class="getClass(item)"
                  >
                    {{ item.sequence_number }}
                    [{{ item.facility }}]
                    ({{ (item.timestamp_from_system_start_ns / 1e9).toFixed(6) }}):
                    {{ item.message }}
                  </v-list-item-title>
                </v-list-item>
              </template>
            </v-virtual-scroll>
          </v-card>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import system_information from '@/store/system-information'
import { Dictionary } from '@/types/common'
import { KernelMessage } from '@/types/system-information/kernel'

export default Vue.extend({
  name: 'Processes',
  data() {
    return {
    }
  },
  computed: {
    messages() {
      return system_information?.kernel_message
    },
  },
  methods: {
    getClass(message: KernelMessage): string {
      const level_color = {
        emerg: 'red darken-1 white--text',
        alert: 'deep-orange darken-4 white--text',
        crit: 'red darken-4 white--text',
        err: 'red white--text',
        warn: 'deep-orange white--text',
        notice: 'blue-grey darken-1 white--text',
        info: 'indigo lighten-5 black--text',
        debug: 'green darken-4 white--text',
      } as Dictionary<string>

      if (level_color[message.level]) {
        const color = level_color[message.level]
        return color
      }

      return ''
    },
  },
})
</script>
