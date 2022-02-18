<template>
  <v-container fluid>
    <v-row>
      <v-col
        cols="12"
        sm="2"
      >
        <v-sheet
          rounded="lg"
          min-height="268"
        >
          <v-card
            class="mx-auto height-limited"
            max-height="700px"
          >
            <v-list shaped>
              <v-list-item-group
                v-model="selected_message_types"
                multiple
              >
                <template v-for="(item, i) in message_types">
                  <v-list-item
                    :key="i"
                    :value="item"
                    active-class="deep-purple--text text--accent-4"
                  >
                    <template #default="{ active }">
                      <v-list-item-content>
                        <v-list-item-title v-text="item" />
                      </v-list-item-content>

                      <v-list-item-action>
                        <v-checkbox
                          :input-value="active"
                          color="deep-purple accent-4"
                        />
                      </v-list-item-action>
                    </template>
                  </v-list-item>
                </template>
              </v-list-item-group>
            </v-list>
          </v-card>
        </v-sheet>
      </v-col>

      <v-col
        cols="12"
        sm="8"
      >
        <v-sheet
          min-height="70vh"
          rounded="lg"
        >
          <v-card>
            <v-virtual-scroll
              :items="messages_in_view"
              :item-height="40"
              height="700px"
            >
              <template #default="{ item }">
                <v-list-item
                  @click="showDetailed(item)"
                >
                  <v-list-item-content>
                    <v-list-item-title>
                      {{ item.timestamp.toLocaleString() }} | {{ item | prettyPrint }}
                    </v-list-item-title>
                  </v-list-item-content>
                </v-list-item>
              </template>
            </v-virtual-scroll>
          </v-card>
        </v-sheet>
      </v-col>

      <v-col
        cols="12"
        sm="2"
      >
        <v-sheet
          rounded="lg"
          min-height="268"
        >
          <v-card v-if="detailed_message">
            <p
              v-for="(item, name, index) in detailed_message"
              :key="index"
            >
              {{ name }}: {{ item }}
            </p>
          </v-card>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>
<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import { Dictionary } from '@/types/common'
import prettify from '@/utils/mavlink_prettifier'

class MAVLinkMessageTable {
  tables: Dictionary<Array<Dictionary<any>>> = {}

  messageTypes: string[] = []

  size_limit = 100 // do not store more than 100 of each message

  constructor() {
    this.tables = {}
  }

  add(message: Dictionary<any>): void {
    const message_timed = message
    message_timed.timestamp = new Date()
    if (message.type in this.tables) {
      this.tables[message.type].push(message_timed)
      if (this.tables[message.type].length > this.size_limit) {
        this.tables[message.type].shift()
      }
    } else {
      this.tables[message.type] = [message_timed]
    }
  }

  getTypes(): string[] {
    return Object.keys(this.tables).sort()
  }

  get(types: string[]): any[] {
    let result: any[] = []
    for (const type of types) {
      result = [...result, ...this.tables[type]]
    }
    return result.sort((x, y) => x.timestamp - y.timestamp)
  }
}

export default Vue.extend({
  name: 'MavlinkInspector',
  components: {
  },
  filters: {
    prettyPrint(message: any) {
      return prettify(message)
    },
  },
  data() {
    return {
      message_types: [] as string[],
      message_table: new MAVLinkMessageTable(),
      message_type_interval: 0,
      messages_in_view_interval: 0,
      messages_in_view: [] as any[],
      selected_message_types: [],
      detailed_message: null as (null | any),
    }
  },
  computed: {
  },
  mounted() {
    this.setupWs()
  },
  beforeDestroy() {
    clearInterval(this.message_type_interval)
    clearInterval(this.messages_in_view_interval)
  },
  methods: {
    update_messages_in_view() {
      this.messages_in_view = this.message_table.get(this.selected_message_types)
    },
    showDetailed(message: any) {
      this.detailed_message = message
    },
    setupWs() {
      this.messages_in_view_interval = setInterval(() => this.update_messages_in_view(), 500)
      this.message_type_interval = setInterval(() => { this.message_types = this.message_table.getTypes() }, 1000)
      mavlink2rest.startListening('').setCallback((receivedMessage) => {
        this.message_table.add(receivedMessage)
      }).setFrequency(0)
    },
  },
})
</script>
<style>
.height-limited {
  overflow-y: auto;
  max-height: 700px;
}
</style>
