<template>
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
    />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import { CumulatedNotification } from '@/types/notifications'

import NotificationManager from './NotificationManager.vue'

export default Vue.extend({
  name: 'NotificationTrayButton',
  components: {
    NotificationManager,
  },
  data() {
    return {
      number_of_notifications: 0,
    }
  },
  methods: {
    updateNumberOfNotifications(showable_notifications: CumulatedNotification[]): void {
      this.number_of_notifications = showable_notifications.length
    },
  },
})
</script>
