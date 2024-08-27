<template>
  <span class="text-button white--text">{{ status_text }}</span>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import frontend from '@/store/frontend'
import { frontend_service } from '@/types/frontend_services'

const notifier = new Notifier(frontend_service)

export default Vue.extend({
  name: 'BackendStatusChecker',
  data: () => ({
    backend_offline: false,
    check_backend_status_task: new OneMoreTime({ delay: 3000, disposeWith: this }),
  }),
  computed: {
    status_text(): string {
      return this.backend_offline ? 'Disconnected' : ''
    },
  },
  mounted() {
    this.check_backend_status_task.setAction(this.checkBackendStatus)
  },
  methods: {
    async checkBackendStatus(): Promise<void> {
      this.backend_offline = frontend.backend_offline
      this.$emit('statusChange', this.backend_offline)
      if (this.backend_offline) {
        const message = 'Could not communicate with BlueOS backend.'
        notifier.pushError('BACKEND_OFFLINE', message)
      }
    },
  },
})
</script>
