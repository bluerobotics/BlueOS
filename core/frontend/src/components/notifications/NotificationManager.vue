<template>
  <v-card width="500">
    <v-app-bar
      elevate-on-scroll
      scroll-target="#notifications-list"
    >
      <v-toolbar-title>Notifications</v-toolbar-title>
      <v-spacer />
      <v-btn
        v-tooltip="'Event log'"
        icon
        @click="$emit('showEventLog')"
      >
        <v-icon>mdi-text-box-search-outline</v-icon>
      </v-btn>
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
          :group-by-service.sync="group_by_service"
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
          v-if="group_by_service && groups_to_show.length != 0"
        >
          <notification-group-card
            v-for="group in groups_to_show"
            :key="`${group.service.name}-${group.level}`"
            :group="group"
            :timestamp="timestamp"
            @dismiss="dismissNotification"
            @showInLog="showInLog"
          />
        </v-list-item-group>

        <v-list-item-group
          v-else-if="!group_by_service && notifications_to_show.length != 0"
        >
          <notification-card
            v-for="notification in notifications_to_show"
            :key="JSON.stringify(notification)"
            :notification="notification"
            :timestamp="timestamp"
            @dismiss="dismissNotification"
            @showInLog="showInLog"
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
import Vue from 'vue'

import alert_engine from '@/alerts/engine'
import alerts from '@/store/alerts'
import { AlertLifecycle } from '@/types/alerts'
import {
  Notification, NotificationGroup,
} from '@/types/notifications'

import NotificationsConfigMenu from './ConfigMenu.vue'
import NotificationCard from './NotificationCard.vue'
import NotificationGroupCard from './NotificationGroupCard.vue'

export default Vue.extend({
  name: 'NotificationManager',
  components: {
    NotificationsConfigMenu,
    NotificationCard,
    NotificationGroupCard,
  },
  data() {
    return {
      group_by_service: true,
      show_config_menu: false,
      show_old_messages: false,
      timestamp: new Date(),
      active_intervals: [] as number[],
    }
  },
  computed: {
    // Newest first
    visible_notifications(): Notification[] {
      return [...this.alert_notifications].sort((a, b) => b.time_created - a.time_created)
    },
    notifications_to_show(): Notification[] {
      return this.visible_notifications
    },
    groups_to_show(): NotificationGroup[] {
      const groups = new Map<string, NotificationGroup>()
      this.visible_notifications.forEach((notification) => {
        const { service, level } = notification
        const group_key = `${service.name}-${level}`
        const group = groups.get(group_key)
        if (group) {
          group.notifications.push(notification)
          return
        }
        groups.set(group_key, { level, service, notifications: [notification] })
      })
      return [...groups.values()].sort((a, b) => a.service.name.localeCompare(b.service.name))
    },
    alert_notifications(): Notification[] {
      return alerts.alerts_list.flatMap((alert) => {
        const rule = alert_engine.getRule(alert.rule_id)
        if (!rule || alert.state !== AlertLifecycle.Fired) return []
        const notification = new Notification(
          rule.level,
          rule.service,
          rule.title,
          rule.description ?? '',
          alert.since.getTime(),
          rule.id,
        )
        return [notification]
      })
    },
  },
  watch: {
    notifications_to_show(): void {
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
      alerts.fired_alerts.forEach((alert) => {
        alert_engine.dismiss(alert.rule_id)
      })
    },
    dismissNotification(notification: Notification): void {
      if (notification.id) {
        alert_engine.dismiss(notification.id)
      }
    },
    showInLog(notification: Notification): void {
      this.$emit('showEventLog', notification.time_created)
    },
    updateTimestamp(): void {
      this.timestamp = new Date()
    },
  },
})
</script>

<style>
</style>
