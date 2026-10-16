<template>
  <v-dialog
    :value="value"
    max-width="1200"
    scrollable
    eager
    @input="$emit('input', $event)"
  >
    <v-card>
      <v-app-bar dense>
        <v-toolbar-title>Event log</v-toolbar-title>
        <v-spacer />
        <v-checkbox
          v-model="follow_logs"
          label="Follow Logs"
          hide-details
          @change="onFollowChange"
        />
        <v-btn
          class="ml-2"
          icon
          @click="$emit('input', false)"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-app-bar>
      <div
        v-if="entries.length === 0"
        class="text-center text--secondary py-8"
      >
        No events yet
      </div>
      <v-virtual-scroll
        v-show="entries.length > 0"
        ref="scroller"
        :items="entries"
        :item-height="ROW_HEIGHT_PX"
        :height="VIEWPORT_HEIGHT_PX"
        bench="10"
        style="font-family: monospace; font-size: 12px;"
        @scroll="onScroll"
      >
        <template #default="{ item }">
          <div
            class="log-row px-4"
            :class="[`${levelColor(item.level)}--text`, { 'highlighted-entry': item.time === highlighted_time }]"
          >
            {{ formatLine(item) }}
          </div>
        </template>
      </v-virtual-scroll>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import { format } from 'date-fns'
import Vue from 'vue'

import notifications from '@/store/notifications'
import { NotificationLevel, notificationLevelColor } from '@/types/notifications'

const BOTTOM_THRESHOLD_PX = 20
const ROW_HEIGHT_PX = 18
const VIEWPORT_HEIGHT_PX = 600

interface LogEntry {
  time: number
  level: NotificationLevel
  service: string
  text: string
}

export default Vue.extend({
  name: 'EventLogModal',
  props: {
    value: {
      type: Boolean,
      required: true,
    },
    focusTime: {
      type: Number,
      default: null,
    },
  },
  data() {
    return {
      ROW_HEIGHT_PX,
      VIEWPORT_HEIGHT_PX,
      follow_logs: true,
      highlighted_time: null as number | null,
    }
  },
  computed: {
    entries(): LogEntry[] {
      return notifications.notifications.map((notification) => ({
        time: notification.time_created,
        level: notification.level,
        service: notification.service.name,
        text: `${notification.type}: ${notification.message}`,
      }))
    },
  },
  watch: {
    entries(): void {
      if (this.follow_logs && this.value) {
        this.scrollToBottom()
      }
    },
    value(opened: boolean): void {
      if (opened) {
        this.$nextTick(this.revealInitialPosition)
      }
    },
  },
  methods: {
    formatLine(entry: LogEntry): string {
      return `${format(entry.time, 'HH:mm:ss.SSS')} [${entry.level.toUpperCase()}] ${entry.service}  ${entry.text}`
    },
    levelColor(level: NotificationLevel): string {
      return notificationLevelColor(level)
    },
    revealInitialPosition(): void {
      this.highlighted_time = null
      if (this.focusTime === null) {
        this.follow_logs = true
        this.scrollToBottom()
        return
      }
      this.scrollToTime(this.focusTime)
    },
    onFollowChange(follow: boolean): void {
      if (follow) {
        this.scrollToBottom()
      }
    },
    // Following stops when the user scrolls away from the bottom and resumes when they get back to it
    onScroll(event: Event): void {
      const container = event.target as HTMLElement
      const distance_to_bottom = container.scrollHeight - container.scrollTop - container.clientHeight
      this.follow_logs = distance_to_bottom <= BOTTOM_THRESHOLD_PX
    },
    scroller(): HTMLElement | undefined {
      return (this.$refs.scroller as Vue | undefined)?.$el as HTMLElement | undefined
    },
    scrollToBottom(): void {
      this.$nextTick(() => {
        const container = this.scroller()
        if (container) {
          container.scrollTop = container.scrollHeight
        }
      })
    },
    scrollToTime(time: number): void {
      const found = this.entries.findIndex((entry) => entry.time >= time)
      const index = found === -1 ? this.entries.length - 1 : found
      if (index < 0) {
        return
      }
      this.follow_logs = false
      this.highlighted_time = this.entries[index].time
      this.$nextTick(() => {
        const container = this.scroller()
        if (container) {
          container.scrollTop = index * ROW_HEIGHT_PX - (container.clientHeight - ROW_HEIGHT_PX) / 2
        }
      })
    },
  },
})
</script>

<style scoped>
.log-row {
  height: 18px;
  line-height: 18px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.highlighted-entry {
  outline: 1px solid currentcolor;
  outline-offset: -1px;
}
</style>
