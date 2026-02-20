<template>
  <v-dialog
    :value="value"
    max-width="1200"
    scrollable
    @input="$emit('input', $event)"
  >
    <v-card>
      <v-app-bar dense>
        <v-spacer />
        <v-toolbar-title>
          Logs for {{ extensionName || extensionIdentifier }}
        </v-toolbar-title>
        <v-spacer />
        <v-checkbox
          v-model="follow_logs"
          label="Follow Logs"
          hide-details
        />
        <v-btn
          class="ml-3"
          icon
          @click="downloadCurrentLog"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn
          class="ml-2"
          icon
          @click="closeModal"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-app-bar>
      <v-sheet>
        <v-card-text
          ref="logContainer"
          style="max-height: calc(600px - 48px); overflow-y: auto;"
        >
          <v-alert
            v-if="modal_error"
            type="error"
            dismissible
            class="ma-2"
            @input="modal_error = null"
          >
            <div class="font-weight-bold mb-1">
              Error
            </div>
            <div>{{ modal_error }}</div>
          </v-alert>
          <div
            v-if="modal_messages.length === 0 && !modal_error"
            class="text-center text--secondary py-8"
          >
            <v-progress-circular
              v-if="requesting_logs"
              indeterminate
              color="primary"
            />
            <div v-else>
              No logs received yet
            </div>
          </div>
          <div
            v-if="modal_messages.length > 0"
            class="logs-container"
            style="padding: 16px; font-family: monospace; font-size: 12px;"
          >
            <div
              v-for="(msg, index) in modal_messages"
              :key="`log-${index}`"
              class="mb-1"
            >
              <!-- eslint-disable -->
              <div
                v-if="!isMessageEmpty(msg)"
                class="log-line"
                v-html="formatLogMessage(msg)"
              />
              <!-- eslint-enable -->
              <br v-else />
            </div>
          </div>
        </v-card-text>
      </v-sheet>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import {
  QueryTarget, Receiver, RecvErr, Sample, Session, Subscriber,
} from '@eclipse-zenoh/zenoh-ts'
import AnsiUp from 'ansi_up'
import { saveAs } from 'file-saver'
import Vue, { PropType } from 'vue'

interface LogMessage {
  message: string
}

const ansi = new AnsiUp()

export default Vue.extend({
  name: 'ExtensionLogsModal',
  props: {
    value: {
      type: Boolean,
      required: true,
    },
    extensionIdentifier: {
      type: String,
      required: true,
    },
    extensionName: {
      type: String,
      default: '',
    },
    zenohSession: {
      type: Object as PropType<Session | null>,
      default: null,
    },
  },
  data() {
    return {
      modal_messages: [] as LogMessage[],
      modal_subscriber: null as Subscriber | null,
      current_modal_topic: '',
      modal_error: null as string | null,
      requesting_logs: false,
      query_timeout: 30000, // high timeout to allow handling large logs
      follow_logs: true,
      scroll_pending: false,
      message_buffer: [] as LogMessage[],
      buffer_flush_timer: null as number | null,
    }
  },
  watch: {
    value(val: boolean) {
      if (val) {
        this.openModal()
      } else {
        this.closeModal()
      }
    },
    follow_logs(val: boolean) {
      if (val) {
        this.scrollToBottom()
      }
    },
  },
  beforeDestroy() {
    this.cleanup()
  },
  methods: {
    async openModal() {
      if (!this.zenohSession) {
        this.modal_error = 'Zenoh session not initialized. Please refresh the page.'
        return
      }

      this.modal_messages = []
      this.modal_error = null

      await this.requestHistoricalLogsForExtension(this.extensionIdentifier)

      if (!this.current_modal_topic) {
        const safeName = this.extensionIdentifier.replace(/\//g, '_').replace(/ /g, '_')
        const topic = `extensions/logs/${safeName}`
        await this.setupModalSubscriber(topic)
      }
    },
    closeModal() {
      this.cleanup()
      this.$emit('input', false)
    },
    cleanup() {
      if (this.modal_subscriber) {
        this.modal_subscriber.undeclare()
        this.modal_subscriber = null
      }
      if (this.buffer_flush_timer) {
        clearTimeout(this.buffer_flush_timer)
        this.buffer_flush_timer = null
      }
      this.flushMessageBuffer()
      this.modal_messages = []
      this.current_modal_topic = ''
      this.modal_error = null
      this.scroll_pending = false
    },
    flushMessageBuffer() {
      if (this.message_buffer.length === 0) {
        return
      }

      const batch = this.message_buffer.splice(0)
      this.modal_messages.push(...batch)

      if (this.modal_messages.length > 5000) {
        const removeCount = this.modal_messages.length - 5000
        this.modal_messages.splice(0, removeCount)
      }

      this.buffer_flush_timer = null
      this.scheduleScroll()
    },
    async setupModalSubscriber(topic: string) {
      if (!this.zenohSession) {
        return
      }

      if (this.current_modal_topic === topic && this.modal_subscriber) {
        return
      }

      if (this.modal_subscriber) {
        await this.modal_subscriber.undeclare()
      }

      this.current_modal_topic = topic
      this.modal_subscriber = await this.zenohSession.declare_subscriber(topic, {
        handler: async (sample: Sample) => {
          const payload = sample.payload()
          const payloadString = payload.to_string()

          let message = payloadString
          try {
            const parsed = JSON.parse(payloadString)
            if (parsed.message != null) {
              message = parsed.message
            } else if (parsed.data != null) {
              message = parsed.data
            }
          } catch {
            // Do nothing
          }

          this.message_buffer.push({ message })

          if (!this.buffer_flush_timer) {
            this.buffer_flush_timer = window.setTimeout(() => {
              this.flushMessageBuffer()
            }, 16) // ~60fps
          }
        },
      })
    },
    async requestHistoricalLogsForExtension(identifier: string) {
      if (!this.zenohSession) {
        return
      }

      this.requesting_logs = true
      this.modal_error = null
      try {
        const queryKey = `kraken/extension/logs/request?extension_name=${encodeURIComponent(identifier)}`
        const receiver: Receiver | void = this.zenohSession.get(queryKey, {
          target: QueryTarget.BestMatching,
        })

        if (!(receiver instanceof Receiver)) {
          this.setErrorAndStop('Failed to create query receiver. No queryable found or connection error.')
          return
        }

        const timeoutPromise = new Promise<null>((resolve) => {
          setTimeout(() => resolve(null), this.query_timeout)
        })

        const replyPromise = receiver.receive()
        const reply = await Promise.race([replyPromise, timeoutPromise])

        if (reply === null) {
          this.setErrorAndStop('Query timeout: No response from zenoh queryable. '
            + 'The service may be unavailable or the extension may not exist.')
          return
        }

        if (reply === RecvErr.Disconnected) {
          this.setErrorAndStop('Query disconnected: Connection to Zenoh was lost.')
          return
        }

        const resp = (reply as { result: () => Sample }).result()
        const payload = resp.payload().to_string()
        let response
        try {
          response = JSON.parse(payload)
        } catch {
          this.setErrorAndStop(`Failed to parse response: ${payload}`)
          return
        }

        if (response.error) {
          this.setErrorAndStop(`Error from queryable: ${response.error}${this.formatErrorType(response.error_type)}`)
          return
        }

        if (Array.isArray(response.messages)) {
          this.modal_messages = response.messages.map((msg: { message?: string }) => ({
            message: msg.message != null ? String(msg.message) : '',
          }))
          this.scrollToBottom()
        }

        if (response.topic && response.topic !== this.current_modal_topic) {
          await this.setupModalSubscriber(response.topic)
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error)
        this.modal_error = `Error requesting historical logs: ${errorMessage}`
        console.error('Error requesting historical logs:', error)
      } finally {
        this.requesting_logs = false
      }
    },
    isMessageEmpty(msg: LogMessage): boolean {
      return String(msg?.message || '').trim().length === 0
    },
    extractLogMessage(msg: LogMessage): string {
      return String(msg?.message || '')
    },
    formatLogMessage(msg: LogMessage): string {
      const message = this.extractLogMessage(msg)
      return ansi.ansi_to_html(message)
    },
    scheduleScroll() {
      if (!this.follow_logs || this.scroll_pending) {
        return
      }
      this.scroll_pending = true
      requestAnimationFrame(() => {
        this.scroll_pending = false
        const container = this.$refs.logContainer as HTMLElement
        if (container) {
          container.scrollTop = container.scrollHeight
        }
      })
    },
    scrollToBottom(force = false) {
      if (!force && !this.follow_logs) {
        return
      }
      this.scroll_pending = false
      this.$nextTick(() => {
        const container = this.$refs.logContainer as HTMLElement
        if (!container) {
          return
        }
        container.scrollTop = container.scrollHeight
      })
    },
    setErrorAndStop(message: string) {
      this.modal_error = message
      this.requesting_logs = false
    },
    formatErrorType(errorType?: string): string {
      return errorType ? ` (${errorType})` : ''
    },
    downloadCurrentLog() {
      const logContent = this.modal_messages
        .map((msg) => String(msg.message || ''))
        .join('\n')
      const safeName = this.extensionIdentifier.replace(/[^a-zA-Z0-9]/g, '_')
      const file = new File([logContent], `${safeName}.log`, { type: 'text/plain' })
      saveAs(file)
    },
  },
})
</script>
