<template>
  <v-container fluid>
    <v-row>
      <v-col
        sm="4"
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
                v-model="selected_topic"
                mandatory
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
                        <v-radio
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
        sm="8"
      >
        <v-card
          v-if="selected_topic"
          outlined
          width="100%"
          height="700px"
        >
          <v-card-title>
            {{ selected_topic }}
          </v-card-title>
          <v-card-text
            style="overflow: auto; height: calc(100% - 48px);"
          >
            <pre>{{ formatMessage(current_message) }}</pre>
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

export default Vue.extend({
  name: 'ZenohInspector',
  data() {
    return {
      topics: [] as string[],
      messages: {} as { [key: string]: ZenohMessage },
      topic_interval: 0,
      selected_topic: null as string | null,
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
    current_message(): ZenohMessage | null {
      if (!this.selected_topic) return null
      return this.messages[this.selected_topic] || null
    }
  },
  async mounted() {
    await this.setupZenoh()
  },
  beforeDestroy() {
    clearInterval(this.topic_interval)
    this.disconnectZenoh()
  },
  methods: {
    formatMessage(message: ZenohMessage | null): string {
      if (!message) return 'No messages received yet'

      try {
        const parsedPayload = JSON.parse(message.payload)
        return JSON.stringify({
          topic: message.topic,
          timestamp: message.timestamp.toLocaleString(),
          payload: parsedPayload
        }, null, 2)
      } catch (e) {
        // If payload is not valid JSON, return the raw message
        return JSON.stringify({
          topic: message.topic,
          timestamp: message.timestamp.toLocaleString(),
          payload: message.payload
        }, null, 2)
      }
    },
    async setupZenoh() {
      try {
        const config = new Config('ws://192.168.31.179:10000')
        this.session = await Session.open(config)
        console.log('[Zenoh] Connected')

        this.subscriber = await this.session.declare_subscriber('**', {
          handler: (sample: Sample) => {
            const topic = sample.keyexpr().toString()
            const message: ZenohMessage = {
              topic,
              payload: sample.payload().to_string(),
              timestamp: new Date()
            }

            // Update messages and topics
            this.$set(this.messages, topic, message)
            if (!this.topics.includes(topic)) {
              this.topics = [...this.topics, topic].sort()
            }

            return Promise.resolve()
          }
        })
        console.log('[Zenoh] Subscribed to all topics')
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
