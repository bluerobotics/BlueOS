<template>
  <div
    class="statustext-widget"
    :class="{ 'statustext-widget--front': is_expanded || !!toast_text }"
  >
    <v-card
      class="statustext-card d-flex align-center flex-nowrap"
      :class="{ 'statustext-card--open': is_expanded }"
      :color="toast_text ? toast_color : undefined"
      :elevation="is_expanded ? 4 : 1"
      height="40"
    >
      <div class="statustext-icon-cell">
        <v-tooltip bottom>
          <template #activator="{ on: tipOn }">
            <v-menu
              v-model="menu_open"
              offset-y
              :close-on-content-click="false"
              min-width="320"
              max-width="480"
            >
              <template #activator="{ on: menuOn, attrs }">
                <v-btn
                  icon
                  small
                  class="statustext-menu-btn"
                  v-bind="attrs"
                  v-on="{ ...tipOn, ...menuOn }"
                >
                  <v-icon>
                    mdi-message-text-outline
                  </v-icon>
                </v-btn>
              </template>
              <v-card>
                <v-card-title class="py-2 subtitle-1">
                  Recent vehicle messages
                </v-card-title>
                <v-divider />
                <v-list v-if="recent_entries.length" dense max-height="320" class="py-0 overflow-y-auto">
                  <v-list-item
                    v-for="entry in recent_entries"
                    :key="entry.id"
                    class="align-start"
                  >
                    <v-list-item-content>
                      <v-list-item-title class="text-wrap text-body-2">
                        <span class="text-caption statustext-muted statustext-time">{{ entry.time }}</span>
                        <span class="mx-1 statustext-muted">·</span>
                        <span>{{ entry.text }}</span>
                      </v-list-item-title>
                    </v-list-item-content>
                  </v-list-item>
                </v-list>
                <v-card-text v-else class="text-caption statustext-muted">
                  No STATUSTEXT messages yet.
                </v-card-text>
              </v-card>
            </v-menu>
          </template>
          <span>MAVLink STATUSTEXT — click for history</span>
        </v-tooltip>
      </div>
      <div class="statustext-body">
        <span class="statustext-message text-body-2">{{ toast_text }}</span>
      </div>
    </v-card>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import Listener from '@/libs/MAVLink2Rest/Listener'

const MAX_RECENT = 20
const TOAST_MS = 5500
const COLLAPSE_MS = 340

function statustextToString(raw: unknown): string {
  if (!Array.isArray(raw) || raw.length === 0) {
    return ''
  }
  const first = raw[0]
  if (typeof first === 'number') {
    return raw
      .map((c: number) => String.fromCharCode(c & 0xff))
      .join('')
      .replace(/\0/g, '')
      .trimEnd()
  }
  return raw.join('')
}

function severityType(sev: unknown): string {
  if (sev && typeof sev === 'object' && 'type' in (sev as Record<string, unknown>)) {
    return String((sev as { type: string }).type)
  }
  return 'MAV_SEVERITY_INFO'
}

function severityToColor(sevType: string): string {
  if ([
    'MAV_SEVERITY_EMERGENCY',
    'MAV_SEVERITY_ALERT',
    'MAV_SEVERITY_CRITICAL',
    'MAV_SEVERITY_ERROR',
  ].includes(sevType)) {
    return 'error'
  }
  if (sevType === 'MAV_SEVERITY_WARNING') {
    return 'warning'
  }
  if (sevType === 'MAV_SEVERITY_NOTICE' || sevType === 'MAV_SEVERITY_INFO') {
    return 'info'
  }
  return 'secondary'
}

type StatustextEntry = { id: number; text: string; time: string }

export default Vue.extend({
  name: 'StatustextWidget',
  data() {
    return {
      listener: undefined as Listener | undefined,
      menu_open: false,
      next_entry_id: 0,
      recent_entries: [] as StatustextEntry[],
      toast_text: '' as string,
      toast_severity: 'MAV_SEVERITY_INFO' as string,
      is_expanded: false,
      hide_timer: 0,
      collapse_timer: 0,
    }
  },
  computed: {
    toast_color(): string {
      return severityToColor(this.toast_severity)
    },
  },
  mounted() {
    this.listener = mavlink2rest.startListening('STATUSTEXT').setCallback((receivedMessage) => {
      const text = statustextToString(receivedMessage?.message?.text)
      if (!text) {
        return
      }
      if (this.recent_entries.length && this.recent_entries[0].text === text) {
        return
      }
      const sevType = severityType(receivedMessage?.message?.severity)
      const time = new Date().toLocaleTimeString(undefined, { hour12: false })
      this.next_entry_id += 1
      this.recent_entries.unshift({ id: this.next_entry_id, text, time })
      if (this.recent_entries.length > MAX_RECENT) {
        this.recent_entries.pop()
      }
      this.showToast(text, sevType)
    }).setFrequency(0)
  },
  beforeDestroy() {
    window.clearTimeout(this.hide_timer)
    window.clearTimeout(this.collapse_timer)
    this.listener?.discard()
  },
  methods: {
    showToast(text: string, sevType: string): void {
      window.clearTimeout(this.hide_timer)
      window.clearTimeout(this.collapse_timer)
      this.toast_text = text
      this.toast_severity = sevType
      this.is_expanded = true
      this.hide_timer = window.setTimeout(() => {
        this.is_expanded = false
        this.collapse_timer = window.setTimeout(() => {
          this.toast_text = ''
        }, COLLAPSE_MS)
      }, TOAST_MS)
    },
  },
})
</script>

<style scoped>
.statustext-widget {
  align-self: center;
  flex: 0 0 auto;
  height: 40px;
  z-index: 1;
}

.statustext-widget--front {
  z-index: 25;
}

.statustext-card {
  overflow: hidden;
  border-radius: 4px;
  max-width: 40px;
  transition: max-width 0.32s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.28s ease;
}

.statustext-card--open {
  max-width: min(400px, calc(100vw - 160px));
}

.statustext-icon-cell {
  flex: 0 0 40px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.statustext-menu-btn {
  margin: 0 !important;
  width: 36px !important;
  height: 36px !important;
}

.statustext-body {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  max-height: 40px;
  padding-right: 10px;
}

.statustext-message {
  display: block;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.statustext-muted {
  color: inherit;
  opacity: 0.68;
}

.statustext-time {
  font-variant-numeric: tabular-nums;
}
</style>
