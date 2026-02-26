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
            <v-card-title>
              <v-text-field
                v-model="topic_filter"
                :label="`Search Topics (${filtered_topics.length})`"
                clearable
                prepend-inner-icon="mdi-magnify"
                single-line
                hide-details
                class="mt-0 pt-0"
              />
            </v-card-title>
            <v-divider />
            <v-list shaped>
              <v-list-item-group
                v-model="selected_topic"
              >
                <template v-for="(item, i) in filtered_topics">
                  <v-list-item
                    :key="i"
                    :value="item"
                    active-class="deep-purple--text text--accent-4"
                  >
                    <template #default="{ active }">
                      <v-list-item-content>
                        <v-list-item-title>
                          {{ item }}
                        </v-list-item-title>
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
          outlined
          width="100%"
          height="700px"
          class="d-flex flex-column"
        >
          <template
            v-if="selected_topic"
          >
            <v-card-title>
              {{ selected_topic }}
              <v-chip
                v-tooltip="'Topic liveliness status'"
                :color="topic_liveliness[selected_topic] === undefined ? 'grey'
                  : (topic_liveliness[selected_topic] ? 'green' : 'red')"
                class="ml-2"
              >
                {{ topic_liveliness[selected_topic] === undefined ? 'Unknown'
                  : (topic_liveliness[selected_topic] ? 'Alive' : 'Dead') }}
              </v-chip>
              <v-chip
                v-tooltip="'Topic type'"
                color="blue"
                class="ml-2"
              >
                {{ topic_types[selected_topic] || 'Unknown' }}
              </v-chip>
              <v-chip
                v-tooltip="'Topic message serialization type'"
                color="purple"
                class="ml-2"
              >
                {{ topic_message_types[selected_topic] || 'Unknown' }}
              </v-chip>
            </v-card-title>

            <v-card-text class="flex-grow-1 overflow-auto">
              <template v-if="isVideoTopic">
                <raw-video-player
                  :video-data="videoData"
                />
              </template>
              <template v-else>
                <pre>{{ formatMessage(current_message) }}</pre>
              </template>
            </v-card-text>
          </template>
          <div
            v-else
            class="select-topic d-flex align-center justify-center fill-height"
          >
            <span style="font-size: 1.5rem; font-weight: 500;">
              Select a topic to view its messages.
            </span>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import {
  Config, Encoding, Sample, SampleKind, Session, Subscriber, ZBytes,
} from '@eclipse-zenoh/zenoh-ts'
import { parse as parseMessageDefinition } from '@foxglove/rosmsg'
import { MessageReader } from '@foxglove/rosmsg2-serialization'
import axios from 'axios'
import Vue from 'vue'

import RawVideoPlayer from './RawVideoPlayer.vue'

interface ZenohMessage {
  topic: string
  payload: ZBytes
  encoding: string
  schema: string | undefined
  timestamp: Date
}

export default Vue.extend({
  name: 'ZenohInspector',
  components: {
    RawVideoPlayer,
  },
  data() {
    return {
      topics: [] as string[],
      messages: {} as { [key: string]: ZenohMessage },
      topic_liveliness: {} as { [key: string]: boolean },
      topic_types: {} as { [key: string]: string },
      topic_message_types: {} as { [key: string]: string },
      selected_topic: null as string | null,
      topic_filter: '',
      session: null as Session | null,
      subscriber: null as Subscriber | null,
      liveliness_subscriber: null as Subscriber | null,
      video_reader: null as MessageReader | null,
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
    },
    isVideoTopic(): boolean {
      return this.selected_topic?.toLowerCase().includes('video') || false
    },
    videoData(): Uint8Array | null {
      if (!this.current_message?.payload || !this.video_reader) {
        return null
      }
      const msg: { data: Uint8Array } = this.video_reader.readMessage(this.current_message.payload.toBytes())
      return msg.data
    },
  },
  async mounted() {
    await this.setupVideoReader()
    await this.setupZenoh()
  },
  beforeDestroy() {
    this.disconnectZenoh()
  },
  methods: {
    async setupVideoReader() {
      const CompressedVideo = await axios.get('/msgs/CompressedVideo.msg').then((response) => response.data as string)
      const definition = parseMessageDefinition(CompressedVideo)
      this.video_reader = new MessageReader(definition)
    },
    formatMessage(message: ZenohMessage | null): string {
      if (!message) return 'No messages received yet'

      // Create the base message object
      const formattedMessage = {
        topic: message.topic,
        timestamp: message.timestamp.toLocaleString(),
        // eslint-disable-next-line no-nested-ternary
        liveliness: this.topic_liveliness[message.topic] === undefined ? 'Unknown'
          : this.topic_liveliness[message.topic] ? 'Alive' : 'Dead',
        topic_type: this.topic_types[message.topic] || 'Unknown',
        message_type: this.topic_message_types[message.topic] || 'Unknown',
        payload: message.payload.toString(),
      }

      if (message.encoding === Encoding.TEXT_PLAIN.toString()) {
        formattedMessage.payload = message.payload.toString()
      } else if (message.encoding === Encoding.APPLICATION_JSON.toString()) {
        formattedMessage.payload = JSON.parse(message.payload.toString())
      } else if (message.encoding === Encoding.ZENOH_BYTES.toString()) {
        try {
          formattedMessage.payload = JSON.parse(message.payload.toString())
        } catch (exception) {
          // Keep the raw payload if it's not valid JSON
          formattedMessage.payload = message.payload.toString()
        }
      }
      return JSON.stringify(formattedMessage, null, 2)
    },

    async setupZenoh() {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const url = `${protocol}://${window.location.host}/zenoh-api/`
        const config = new Config(url)
        this.session = await Session.open(config)

        // Setup regular message subscriber
        this.subscriber = await this.session.declareSubscriber('**', {
          handler: async (sample: Sample) => {
            const topic = sample.keyexpr().toString()
            const payload = sample.payload()
            const [encoding, schema] = sample.encoding().toString().split(';')

            const message: ZenohMessage = {
              topic,
              payload,
              encoding,
              schema,
              timestamp: new Date(),
            }

            // Update messages and topics
            this.$set(this.messages, topic, message)
            if (!this.topics.includes(topic)) {
              this.topics = [...this.topics, topic].sort()
            }

            return Promise.resolve()
          },
        })

        // Setup liveliness subscriber
        const lv_ke = '@/**/@ros2_lv/**'

        this.liveliness_subscriber = await this.session.liveliness().declareSubscriber(lv_ke, {
          handler: (sample: Sample) => {
            // Parse the liveliness token using regex
            // eslint-disable-next-line max-len
            // https://github.com/eclipse-zenoh/zenoh-plugin-ros2dds/blob/865d3db009d0d2635826700a35483e88a077967d/zenoh-plugin-ros2dds/src/liveliness_mgt.rs#L202
            const keyexpr = sample.keyexpr().toString()
            // eslint-disable-next-line max-len
            const match = keyexpr.match(/@\/(?<zenoh_id>[^/]+)\/@ros2_lv\/(?<type>MP|MS|SS|SC|AS|AC)\/(?<ke>[^/]+)\/(?<typ>[^/]+)(?:\/(?<qos_ke>[^/]+))?/)

            if (!match) {
              return Promise.resolve()
            }

            const { type, ke, typ } = match.groups || {}
            const topic = ke.replace(/§/g, '/')
            const messageTyp = typ.replace(/§/g, '/')

            const isAlive = sample.kind() === SampleKind.PUT

            // Update liveliness state and type
            this.$set(this.topic_liveliness, topic, isAlive)
            this.$set(this.topic_types, topic, type)
            this.$set(this.topic_message_types, topic, messageTyp)

            // Add to topics if not already present
            if (!this.topics.includes(topic)) {
              this.topics = [...this.topics, topic].sort()
            }

            return Promise.resolve()
          },
          history: true, // Enable history to get initial state
        })
      } catch (error) {
        console.error('[Zenoh] Connection error:', error)
      }
    },
    async disconnectZenoh() {
      await this.session?.close()
      this.subscriber?.undeclare()
      this.liveliness_subscriber?.undeclare()

      this.session = null
      this.subscriber = null
      this.liveliness_subscriber = null
    },
  },
})
</script>
<style>
.height-limited {
  overflow-y: auto;
  max-height: 700px;
}

.select-topic {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  text-align: center;
}
</style>
