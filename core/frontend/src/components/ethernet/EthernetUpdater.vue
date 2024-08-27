<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import ethernet from '@/store/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(ethernet_service)

export default Vue.extend({
  name: 'EthernetUpdater',
  data() {
    return {
      fetch_available_interfaces_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
    }
  },
  mounted() {
    this.fetch_available_interfaces_task.setAction(this.fetchAvailableInterfaces)
  },
  methods: {
    async fetchAvailableInterfaces(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${ethernet.API_URL}/ethernet`,
        timeout: 5000,
      })
        .then((response) => {
          ethernet.setInterfaces(response.data)
        })
        .catch((error) => {
          ethernet.setInterfaces([])
          notifier.pushBackError('ETHERNET_AVAILABLE_FETCH_FAIL', error)
        })
    },
  },
})
</script>
