<template>
  <v-lazy
    :options="{ threshold: .5 }"
    transition="slide-x-transition"
  >
    <v-card
      elevation="0"
      @click="toggleReveal"
    >
      <v-list-item>
        <v-list-item-icon>
          <v-icon :color="level_color">
            {{ level_icon }}
          </v-icon>
        </v-list-item-icon>

        <v-list-item-content>
          <v-list-item-title>{{ notification.service.name }}</v-list-item-title>
          <v-list-item-subtitle>{{ notification.type }}</v-list-item-subtitle>
          <v-slide-y-reverse-transition
            leave-absolute
            hide-on-leave
          >
            <v-list-item-subtitle
              v-if="!reveal"
            >
              {{ notification.message }}
            </v-list-item-subtitle>
          </v-slide-y-reverse-transition>
          <v-slide-y-transition
            leave-absolute
            hide-on-leave
          >
            <v-list-item-subtitle
              v-if="reveal"
              class="really-wrap-text"
            >
              {{ notification.message }}
            </v-list-item-subtitle>
          </v-slide-y-transition>
          <v-list-item-subtitle>{{ time_since }} ({{ count }} times)</v-list-item-subtitle>
        </v-list-item-content>

        <v-list-item-action>
          <v-btn icon>
            <v-icon
              color="grey lighten-1"
              size="medium"
              @click="dismiss"
            >
              mdi-close
            </v-icon>
          </v-btn>
        </v-list-item-action>
      </v-list-item>
      <v-divider />
    </v-card>
  </v-lazy>
</template>

<script lang="ts">
import { formatDistance } from 'date-fns'
import Vue, { PropType } from 'vue'

import { Notification, NotificationLevel } from '@/types/notifications'

export default Vue.extend({
  name: 'NotificationCard',
  props: {
    count: {
      type: Number,
      required: true,
    },
    notification: {
      type: Object as PropType<Notification>,
      required: true,
    },
    timestamp: {
      type: Date,
      required: true,
    },
  },
  data() {
    return {
      reveal: false,
    }
  },
  computed: {
    time_since(): string {
      const date_now = new Date(this.timestamp)
      const date_notification = new Date(this.notification.time_created)
      return `${formatDistance(date_now, date_notification)} ago`
    },
    level_icon(): string {
      switch (this.notification.level) {
        case NotificationLevel.Success: return 'mdi-check-bold'
        case NotificationLevel.Error: return 'mdi-close-circle'
        case NotificationLevel.Info: return 'mdi-information'
        case NotificationLevel.Warning: return 'mdi-alert'
        case NotificationLevel.Critical: return 'mdi-skull'
        default: return 'mdi-help-circle'
      }
    },
    level_color(): string {
      switch (this.notification.level) {
        case NotificationLevel.Success: return 'success'
        case NotificationLevel.Error: return 'error'
        case NotificationLevel.Info: return 'info'
        case NotificationLevel.Warning: return 'warning'
        case NotificationLevel.Critical: return 'critical'
        default: return 'info'
      }
    },
  },
  methods: {
    dismiss(): void {
      this.$emit('dismiss', this.notification)
    },
    toggleReveal(): void {
      this.reveal = !this.reveal
    },
  },
})
</script>

<style scoped>
.really-wrap-text {
  -webkit-line-clamp: unset !important;
}
</style>
