<template>
  <v-container />
</template>
<script lang="ts">
import Vue from 'vue'

import notifications from '@/store/notifications'
import { update_time_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

export default Vue.extend({
  name: 'UpdateTime',
  mounted() {
    this.set_time()
  },
  methods: {
    async set_time() {
      await back_axios({
        url: '/commander/v1.0/set_time',
        method: 'post',
        params: {
          unix_time_seconds: Math.round(new Date().getTime() / 1000),
          i_know_what_i_am_doing: true,
        },
        timeout: 10000,
      })
        .catch((error) => {
        // Connection lost/timeout, normal when we are turnning off/rebooting
          if (error.code === 'ECONNABORTED') {
            this.set_time()
            return
          }

          const message = `Failed to commit operation: ${error.message}`
          notifications.pushError({ service: update_time_service, type: 'UPDATE_TIME_FAIL', message })
        })
    },
  },
})
</script>
