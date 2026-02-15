<template>
  <v-card width="500">
    <v-app-bar
      elevate-on-scroll
      scroll-target="#notifications-list"
    >
      <v-toolbar-title>Notifications</v-toolbar-title>
      <v-spacer />
      <v-btn
        icon
        @click="dismissAllNotifications()"
      >
        <v-icon>mdi-broom</v-icon>
      </v-btn>
      <v-menu
        v-model="show_config_menu"
        :close-on-content-click="false"
        :nudge-x="400"
        offset-y
      >
        <template #activator="{ on, attrs }">
          <v-btn
            icon
            v-bind="attrs"
            v-on="on"
          >
            <v-icon>mdi-cog</v-icon>
          </v-btn>
        </template>
        <notifications-config-menu
          :show-old.sync="show_old_messages"
        />
      </v-menu>
    </v-app-bar>

    <v-sheet
      id="notifications-list"
      class="overflow-y-auto"
    >
      <v-list
        three-line
        dense
        class="overflow-y-auto"
        tile
        max-height="50vh"
      >
        <v-list-item-group
          v-if="notifications_to_show.length != 0"
        >
          <notification-card
            v-for="{ notification, count } in notifications_to_show"
            :key="JSON.stringify(notification)"
            :notification="notification"
            :count="count"
            :timestamp="timestamp"
            @dismiss="dismissNotification"
          />
        </v-list-item-group>

        <v-card
          v-else
          elevation="0"
        >
          <v-card-text class="text-center">
            No notifications to display :)
          </v-card-text>
        </v-card>
      </v-list>
    </v-sheet>
  </v-card>
</template>

<script lang="ts">
import { differenceInSeconds } from 'date-fns'
import Vue from 'vue'

import notifications from '@/store/notifications'
import { CumulatedNotification, Notification } from '@/types/notifications'

import NotificationsConfigMenu from './ConfigMenu.vue'
import NotificationCard from './NotificationCard.vue'

export default Vue.extend({
  name: 'NotificationManager',
  components: {
    NotificationsConfigMenu,
    NotificationCard,
  },
  data() {
    return {
      show_config_menu: false,
      show_old_messages: false,
      timestamp: new Date(),
      seconds_recent: 60,
      active_intervals: [] as number[],
      max_number_notifications: 100,
    }
  },
  computed: {
    notifications(): CumulatedNotification[] {
      return notifications.active_cumulated_notifications
    },
    recent_notifications(): CumulatedNotification[] {
      return this.notifications.filter((cumulated) => {
        const date_now = new Date()
        const date_notification = new Date(cumulated.notification.time_created)
        return differenceInSeconds(date_now, date_notification) < this.seconds_recent
      }).slice(-this.max_number_notifications)
    },
    notifications_to_show(): CumulatedNotification[] {
      const notifications_to_show = this.show_old_messages ? this.notifications : this.recent_notifications
      // Returning the notifications reversed to show the last ones first
      return notifications_to_show.reverse()
    },
  },
  watch: {
    notifications(): void {
      this.$emit('notificationsChange', this.notifications_to_show)
    },
  },
  mounted() {
    const interval = setInterval(this.updateTimestamp, 1000)
    this.active_intervals.push(interval)
  },
  beforeDestroy() {
    this.active_intervals.forEach((interval) => clearInterval(interval))
  },
  methods: {
    dismissAllNotifications(): void {
      notifications.notifications.forEach((notification) => {
        this.dismissNotification(notification)
      })
    },
    dismissNotification(notification: Notification): void {
      notifications.dismissNotification(notification)
    },
    updateTimestamp(): void {
      this.timestamp = new Date()
    },
  },
})
</script>
