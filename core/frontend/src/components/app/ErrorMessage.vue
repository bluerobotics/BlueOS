<template>
  <v-snackbar
    v-model="show"
    timeout="-1"
  >
    {{ message }}

    <template #action="{ attrs }">
      <v-btn
        color="pink"
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

import error_message_manager from '@/libs/error-message'

export default Vue.extend({
  name: 'ErrorMessage',
  data() {
    return {
      message: '',
      show: false,
    }
  },
  mounted() {
    error_message_manager.addCallback((message) => {
      this.message = message
      this.show = true
    })
  },
})
</script>
