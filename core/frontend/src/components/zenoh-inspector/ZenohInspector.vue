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
              v-model="topic_filter"
              class="ma-2"
              label="Search Topics"
              clearable
              prepend-inner-icon="mdi-magnify"
            />
            <v-list shaped>
              <v-list-item-group
                v-model="selected_topics"
                multiple
              >
                <template v-for="(item, i) in filtered_topics">
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
                      {{ item.timestamp.toLocaleString() }} | {{ item.topic }}: {{ item.payload }}
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
import { Config, Session, Subscriber, Sample } from '@eclipse-zenoh/zenoh-ts'

interface ZenohMessage {
  topic: string
  payload: string
  timestamp: Date
}

class ZenohMessageTable {
  messages: ZenohMessage[] = []
  topics: Set<string> = new Set()
  size_limit = 1000 // Maximum number of messages to store

  add(topic: string, payload: string): void {
    const message: ZenohMessage = {
      topic,
      payload,
      timestamp: new Date()
    }

    this.messages.push(message)
    this.topics.add(topic)

    if (this.messages.length > this.size_limit) {
      this.messages.shift()
    }
  }

  getTopics(): string[] {
    return Array.from(this.topics).sort()
  }

  getMessages(selectedTopics: string[]): ZenohMessage[] {
    if (selectedTopics.length === 0) return []
    return this.messages
      .filter(msg => selectedTopics.includes(msg.topic))
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
  }
}

export default Vue.extend({
  name: 'ZenohInspector',
  data() {
    return {
      topics: [] as string[],
      message_table: new ZenohMessageTable(),
      topic_interval: 0,
      messages_in_view_interval: 0,
      messages_in_view: [] as ZenohMessage[],
      selected_topics: [] as string[],
      detailed_message: null as (null | ZenohMessage),
      topic_filter: '',
      session: null as Session | null,
      subscriber: null as Subscriber | null,
    }
  },
  computed: {
    filtered_topics(): string[] {
      try {
        return this.topics.filter(
          (name: string) => name.toLowerCase().includes(this.topic_filter.toLowerCase().trim()),
        )
      } catch {
        return this.topics
      }
    },
  },
  async mounted() {
    await this.setupZenoh()
  },
  beforeDestroy() {
    clearInterval(this.topic_interval)
    clearInterval(this.messages_in_view_interval)
    this.disconnectZenoh()
  },
  methods: {
    update_messages_in_view() {
      this.messages_in_view = this.message_table.getMessages(this.selected_topics)
    },
    showDetailed(message: ZenohMessage) {
      this.detailed_message = message
    },
    async setupZenoh() {
      try {
        const config = new Config('ws://192.168.31.179:10000')
        this.session = await Session.open(config)
        console.log('[Zenoh] Connected')

        this.subscriber = await this.session.declare_subscriber('**', {
          handler: (sample: Sample) => {
            const topic = sample.keyexpr().toString()
            const payload = sample.payload().to_string()
            this.message_table.add(topic, payload)
            return Promise.resolve()
          }
        })
        console.log('[Zenoh] Subscribed to all topics')

        this.messages_in_view_interval = setInterval(() => this.update_messages_in_view(), 500)
        this.topic_interval = setInterval(() => { this.topics = this.message_table.getTopics() }, 1000)
      } catch (error) {
        console.error('[Zenoh] Connection error:', error)
      }
    },
    async disconnectZenoh() {
      if (this.session) {
        await this.session.close()
        console.log('[Zenoh] Disconnected')
        this.session = null
        this.subscriber = null
      }
    }
  },
})
</script>
<style>
.height-limited {
  overflow-y: auto;
  max-height: 700px;
}
</style>
