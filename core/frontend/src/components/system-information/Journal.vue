<template>
  <v-container fluid>
    <v-row>
      <v-col>
        <v-sheet
          min-height="70vh"
          rounded="lg"
        >
          <v-card elevation="0">
            <v-virtual-scroll
              :item-height="20"
              :items="entries"
              height="700px"
            >
              <template #default="{ item }">
                <v-list-item>
                  <v-list-item-content>
                    <v-list-item-title
                      class="pa-0"
                      :class="priorityClass(item.priority)"
                    >
                      {{ formatTimestamp(item.timestamp) }}
                      [{{ priorityLabel(item.priority) }}]
                      <span v-if="sourceLabel(item)">{{ sourceLabel(item) }}:</span>
                      {{ item.message }}
                    </v-list-item-title>
                  </v-list-item-content>
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

import system_information, { FetchType } from '@/store/system-information'
import { JournalEntry } from '@/types/system-information/journal'

export default Vue.extend({
  name: 'Journal',
  computed: {
    entries(): JournalEntry[] {
      return system_information?.journal_entries ?? []
    },
  },
  created() {
    system_information.fetchSystemInformation(FetchType.JournalType)
  },
  methods: {
    formatTimestamp(value?: string): string {
      if (!value) {
        return 'Unknown time'
      }
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) {
        return value
      }
      return date.toLocaleString()
    },
    sourceLabel(entry: JournalEntry): string | null {
      if (entry.identifier) {
        return entry.identifier
      }
      return null
    },
    priorityLabel(priority?: number): string {
      const map: Record<number, string> = {
        0: 'Emergency',
        1: 'Alert',
        2: 'Critical',
        3: 'Error',
        4: 'Warning',
        5: 'Notice',
        6: 'Info',
        7: 'Debug',
      }
      if (priority === undefined || priority === null) {
        return map[6]
      }
      return map[priority] ?? map[6]
    },
    priorityClass(priority?: number): string {
      const priorityColors: Record<number, string> = {
        0: 'red darken-4 white--text',
        1: 'deep-orange darken-3 white--text',
        2: 'pink darken-2 white--text',
        3: 'red darken-1 white--text',
        4: 'amber darken-2 black--text',
        5: 'cyan darken-1 white--text',
        6: 'indigo lighten-5 black--text',
        7: 'green darken-3 white--text',
      }
      // eslint-disable-next-line eqeqeq
      if (priority == undefined) {
        return priorityColors[6]
      }
      return priorityColors[priority] ?? priorityColors[6]
    },
  },
})
</script>
