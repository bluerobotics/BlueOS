<template>
  <v-menu
    :close-on-content-click="false"
    nudge-left="500"
    nudge-bottom="30"
  >
    <template
      #activator="{on, attrs}"
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
          color="red"
          overlap
        >
          <v-icon color="white">
            mdi-bell
          </v-icon>
        </v-badge>
      </v-card>
    </template>
    <notification-manager />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import notifications from '@/store/notifications'

import NotificationManager from './NotificationManager.vue'

export default Vue.extend({
  name: 'NotificationTrayButton',
  components: {
    NotificationManager,
  },
  computed: {
    number_of_notifications(): number {
      return notifications.active_cumulated_notifications.length
    },
  },
})
</script>

<style>
</style>
