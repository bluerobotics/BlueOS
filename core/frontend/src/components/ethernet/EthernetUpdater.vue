<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import { OneMoreTime } from '@/one-more-time'
import ethernet from '@/store/ethernet'

export default Vue.extend({
  name: 'EthernetUpdater',
  data() {
    return {
      fetch_available_interfaces_task: new OneMoreTime({ delay: 5000, disposeWith: this, autostart: false }),
    }
  },
  async mounted() {
    try {
      await this.fetchAvailableEthernetInterfaces()
    } finally {
      ethernet.setUpdatingInterfaces(false)
      this.fetch_available_interfaces_task.setAction(this.fetchAvailableEthernetInterfaces)
      this.fetch_available_interfaces_task.start()
    }
  },
  methods: {
    async fetchAvailableEthernetInterfaces(): Promise<void> {
      await ethernet.getAvailableEthernetInterfaces()
        .then((response) => {
          ethernet.setInterfaces(response.data)
        })
    },
  },
})
</script>
