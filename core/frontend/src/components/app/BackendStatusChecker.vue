<template>
  <span class="text-button white--text">{{ status_text }}</span>
</template>

<script lang="ts">
import Vue from 'vue'

import frontend from '@/store/frontend'
import notifications from '@/store/notifications'
import { frontend_service } from '@/types/frontend_services'
import { callPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'BackendStatusChecker',
  data: () => ({
    backend_offline: false,
  }),
  computed: {
    status_text(): string {
      return this.backend_offline ? 'Disconnected' : ''
    },
  },
  mounted() {
    callPeriodically(this.checkBackendStatus, 3000)
  },
  methods: {
    async checkBackendStatus(): Promise<void> {
      this.backend_offline = frontend.backend_offline
      this.$emit('statusChange', this.backend_offline)
      if (this.backend_offline) {
        const message = 'Could not communicate with BlueOS backend.'
        notifications.pushError({ service: frontend_service, type: 'BACKEND_OFFLINE', message })
      }
    },
  },
})
</script>
