<template>
  <v-snackbar
    v-model="show"
    :timeout="timeout"
  >
    {{ message }}

    <template #action="{ attrs }">
      <v-btn
        :color="color"
        text
        v-bind="attrs"
        @click="show = false"
      >
        Close
      </v-btn>
    </template>
  </v-snackbar>
</template>

<script lang="ts">
import Vue from 'vue'

import message_manager, { MessageLevel } from '@/libs/message-manager'

export default Vue.extend({
  name: 'ErrorMessage',
  data() {
    return {
      level: undefined as MessageLevel|undefined,
      message: '',
      show: false,
    }
  },
  computed: {
    color(): string {
      switch (this.level) {
        case MessageLevel.Success:
          return 'success'
        case MessageLevel.Error:
          return 'error'
        case MessageLevel.Info:
          return 'info'
        case MessageLevel.Warning:
          return 'warning'
        case MessageLevel.Critical:
          return 'critical'
        default:
          return 'info'
      }
    },
    timeout(): number {
      switch (this.level) {
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
  mounted() {
    message_manager.addCallback((level: MessageLevel, message: string) => {
      this.level = level
      this.message = message
      this.show = true
    })
  },
})
</script>
