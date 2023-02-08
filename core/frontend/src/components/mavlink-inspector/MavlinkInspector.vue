<template>
  <v-container fluid>
    <v-row>
      <v-col
        sm="3"
      >
        <v-sheet
          rounded="lg"
          min-height="268"
        >
          <v-card
            class="mx-auto height-limited"
            max-height="700px"
          >
            <v-text-field
              v-model="message_filter"
              class="ma-2"
              label="Search"
              clearable
              prepend-inner-icon="mdi-magnify"
            />
            <v-list shaped>
              <v-list-item-group
                v-model="selected_message_types"
                multiple
              >
                <template v-for="(item, i) in filtered_messages">
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
        sm="6"
        height="700px"
      >
        <v-sheet
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
        sm="3"
      >
        <v-card
          v-if="detailed_message"
          outlined
          width="100%"
        >
          <v-card-text
            style="overflow: auto;"
          >
            <pre> {{ detailed_message }} </pre>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import { Message } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest'
import { Dictionary } from '@/types/common'
import prettify from '@/utils/mavlink_prettifier'

class MAVLinkMessageTable {
  tables: Dictionary<Array<Message>> = {}

  messageTypes: string[] = []

  size_limit = 100 // do not store more than 100 of each message

  constructor() {
    this.tables = {}
  }

  add(mavlink_message: Message): void {
    const message_timed = mavlink_message
    message_timed.timestamp = new Date()
    const { message } = mavlink_message
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

  get(types: string[]): Message[] {
    let result: Message[] = []
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
    prettyPrint(mavlink_message: Message) {
      return prettify(mavlink_message.message)
    },
  },
  data() {
    return {
      message_types: [] as string[],
      message_table: new MAVLinkMessageTable(),
      message_type_interval: 0,
      messages_in_view_interval: 0,
      messages_in_view: [] as Message[],
      selected_message_types: [],
      detailed_message: null as (null | Message),
      message_filter: '',
    }
  },
  computed: {
    filtered_messages(): string[] {
      try {
        return this.message_types.filter(
          (name: string) => name.toLowerCase().includes(this.message_filter.toLowerCase().trim()),
        )
      } catch {
        return this.message_types
      }
    },
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
    showDetailed(message: Message) {
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
