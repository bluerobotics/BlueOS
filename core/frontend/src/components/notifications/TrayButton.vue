<template>
  <div style="display: contents;">
    <v-menu
      eager
      :close-on-content-click="false"
      nudge-left="500"
      nudge-bottom="30"
    >
      <template
        #activator="{ on, attrs }"
      >
        <v-card
          id="notifications-tray-menu-button"
          elevation="0"
          color="transparent"
          v-bind="attrs"
          v-on="on"
        >
          <v-badge
            :content="number_of_notifications"
            :value="number_of_notifications"
            color="error"
            overlap
          >
            <v-icon color="white">
              mdi-bell
            </v-icon>
          </v-badge>
        </v-card>
      </template>
      <notification-manager
        @notificationsChange="updateNumberOfNotifications"
        @showEventLog="showEventLog"
      />
    </v-menu>
    <event-log-modal
      v-model="show_event_log"
      :focus-time="event_log_focus_time"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import { Notification } from '@/types/notifications'

import EventLogModal from './EventLogModal.vue'
import NotificationManager from './NotificationManager.vue'

export default Vue.extend({
  name: 'NotificationTrayButton',
  components: {
    EventLogModal,
    NotificationManager,
  },
  data() {
    return {
      number_of_notifications: 0,
      show_event_log: false,
      event_log_focus_time: null as number | null,
    }
  },
  methods: {
    showEventLog(time?: number): void {
      this.event_log_focus_time = time ?? null
      this.show_event_log = true
    },
    updateNumberOfNotifications(showable_notifications: Notification[]): void {
      this.number_of_notifications = showable_notifications.length
    },
  },
})
</script>

<style>
</style>
