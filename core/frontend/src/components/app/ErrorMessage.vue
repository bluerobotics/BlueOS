<template>
  <v-snackbar
    v-model="show"
    timeout="-1"
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

import message_manager, { MessageLevel } from '@/libs/error-message'

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
          return 'green'
        case MessageLevel.Error:
          return 'pink'
        case MessageLevel.Info:
          return 'grey'
        case MessageLevel.Warning:
          return 'yellow'
        case MessageLevel.Critical:
          return 'red'
        default:
          return 'grey'
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
