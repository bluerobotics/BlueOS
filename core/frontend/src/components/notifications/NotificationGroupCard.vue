<template>
  <div>
    <v-lazy
      :options="{ threshold: .5 }"
      transition="slide-x-transition"
    >
      <v-card
        elevation="0"
        @click="expanded = !expanded"
      >
        <v-list-item>
          <v-list-item-icon>
            <v-icon :color="level_color">
              {{ level_icon }}
            </v-icon>
          </v-list-item-icon>

          <v-list-item-content>
            <v-list-item-title>{{ group.service.name }}</v-list-item-title>
            <template v-if="types_summary.length === 1">
              <v-list-item-subtitle>{{ types_summary[0] }}</v-list-item-subtitle>
              <v-list-item-subtitle>{{ latest.message }}</v-list-item-subtitle>
            </template>
            <v-list-item-subtitle
              v-else
              class="really-wrap-text"
            >
              <div
                v-for="type in types_summary"
                :key="type"
              >
                {{ type }}
              </div>
            </v-list-item-subtitle>
            <v-list-item-subtitle>
              {{ time_since }} ({{ group.notifications.length }} notifications)
            </v-list-item-subtitle>
          </v-list-item-content>

          <v-list-item-action>
            <v-btn
              icon
              @click.stop="dismissAll"
            >
              <v-icon
                color="grey lighten-1"
                size="medium"
              >
                mdi-close
              </v-icon>
            </v-btn>
          </v-list-item-action>
        </v-list-item>
        <v-divider />
      </v-card>
    </v-lazy>

    <div
      v-if="expanded"
      class="ml-4"
    >
      <notification-card
        v-for="notification in group.notifications"
        :key="JSON.stringify(notification)"
        :notification="notification"
        :show-service="false"
        :timestamp="timestamp"
        @dismiss="dismiss"
        @showInLog="$emit('showInLog', $event)"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { formatDistance } from 'date-fns'
import Vue, { PropType } from 'vue'

import {
  Notification, NotificationGroup, notificationLevelColor,
  notificationLevelIcon,
} from '@/types/notifications'

import NotificationCard from './NotificationCard.vue'

export default Vue.extend({
  name: 'NotificationGroupCard',
  components: {
    NotificationCard,
  },
  props: {
    group: {
      type: Object as PropType<NotificationGroup>,
      required: true,
    },
    timestamp: {
      type: Date,
      required: true,
    },
  },
  data() {
    return {
      expanded: false,
    }
  },
  computed: {
    latest(): Notification {
      return this.group.notifications[0]
    },
    level_icon(): string {
      return notificationLevelIcon(this.latest.level)
    },
    level_color(): string {
      return notificationLevelColor(this.latest.level)
    },
    time_since(): string {
      return `${formatDistance(new Date(this.latest.time_created), new Date(this.timestamp))} ago`
    },
    types_summary(): string[] {
      return [...new Set(this.group.notifications.map(({ type }) => type))]
    },
  },
  methods: {
    dismiss(notification: Notification): void {
      this.$emit('dismiss', notification)
    },
    dismissAll(): void {
      this.group.notifications.forEach(this.dismiss)
    },
  },
})
</script>

<style scoped>
.really-wrap-text {
  -webkit-line-clamp: unset !important;
}
</style>
