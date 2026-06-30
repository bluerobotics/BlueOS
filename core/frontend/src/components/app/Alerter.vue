<template>
  <div class="alerter-stack">
    <v-slide-y-reverse-transition
      group
      leave-absolute
    >
      <v-alert
        v-for="alert in alerts"
        :key="alert.id"
        :value="true"
        :type="alertType(alert.level)"
        class="alerter-item"
        dense
        dismissible
        elevation="6"
        @input="dismiss(alert.id)"
      >
        {{ alert.message }}
      </v-alert>
    </v-slide-y-reverse-transition>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import message_manager, { MessageLevel } from '@/libs/message-manager'

const MAX_VISIBLE = 5
const DRAIN_INTERVAL_MS = 1000

interface AlertEntry {
  id: number
  level: MessageLevel
  message: string
}

let nextId = 0

export default Vue.extend({
  name: 'ErrorMessage',
  data() {
    return {
      alerts: [] as AlertEntry[],
      queue: [] as AlertEntry[],
      drainTimer: null as ReturnType<typeof setInterval> | null,
      boundCallback: null as ((level: MessageLevel, msg: string) => void) | null,
    }
  },
  mounted() {
    this.boundCallback = (level: MessageLevel, message: string) => {
      nextId += 1
      const entry = { id: nextId, level, message }
      if (this.alerts.length < MAX_VISIBLE) {
        this.showAlert(entry)
      } else {
        this.queue.push(entry)
        this.startDrain()
      }
    }
    message_manager.addCallback(this.boundCallback)
  },
  beforeDestroy() {
    if (this.boundCallback) {
      message_manager.removeCallback(this.boundCallback)
      this.boundCallback = null
    }
    this.stopDrain()
  },
  methods: {
    showAlert(entry: AlertEntry) {
      this.alerts.push(entry)
      const timeout = this.getTimeout(entry.level)
      if (timeout > 0) {
        setTimeout(() => this.dismiss(entry.id), timeout)
      }
    },
    dismiss(id: number) {
      const idx = this.alerts.findIndex((a) => a.id === id)
      if (idx !== -1) {
        this.alerts.splice(idx, 1)
        this.promoteFromQueue()
      }
    },
    promoteFromQueue() {
      while (this.queue.length > 0 && this.alerts.length < MAX_VISIBLE) {
        this.showAlert(this.queue.shift()!)
      }
      if (this.queue.length === 0) {
        this.stopDrain()
      }
    },
    startDrain() {
      if (this.drainTimer) return
      this.drainTimer = setInterval(() => {
        const evictIdx = this.alerts.findIndex((a) => this.getTimeout(a.level) > 0)
        if (evictIdx !== -1) {
          this.dismiss(this.alerts[evictIdx].id)
        } else if (this.queue.length > 0 && this.alerts.length > 0) {
          this.dismiss(this.alerts[0].id)
        }
      }, DRAIN_INTERVAL_MS)
    },
    stopDrain() {
      if (this.drainTimer) {
        clearInterval(this.drainTimer)
        this.drainTimer = null
      }
    },
    alertType(level: MessageLevel): string {
      switch (level) {
        case MessageLevel.Success:
          return 'success'
        case MessageLevel.Error:
        case MessageLevel.Critical:
          return 'error'
        case MessageLevel.Warning:
          return 'warning'
        default:
          return 'info'
      }
    },
    getTimeout(level: MessageLevel): number {
      switch (level) {
        case MessageLevel.Success:
        case MessageLevel.Info:
          return 5000
        case MessageLevel.Warning:
          return 7000
        default:
          return -1
      }
    },
  },
})
</script>

<style scoped>
.alerter-stack {
  position: fixed;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  min-width: 344px;
  max-width: 672px;
}

.alerter-item {
  margin-bottom: 8px;
}
</style>
