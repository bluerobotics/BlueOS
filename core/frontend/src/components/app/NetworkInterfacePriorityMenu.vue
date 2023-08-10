<template>
  <v-card class="pa-2 mx-auto" min-width="100%">
    <v-list>
      <v-card-subtitle class="text-md-center" max-width="30">
        Move network interfaces over
        to change network access priority.<br>Applied changes require a <b>system reboot</b>.
      </v-card-subtitle>
      <draggable v-model="interfaces">
        <v-card
          v-for="element, index in interfaces"
          :key="index"
          class="pl-3 ma-2 pa-1 d-flex align-center justify-center"
          style="cursor: pointer"
        >
          {{ order(index + 1) }}
          <v-spacer />
          {{ element.name }}
          <v-spacer />
          <v-icon
            v-text="'mdi-drag'"
          />
        </v-card>
      </draggable>
      <v-progress-linear
        v-if="is_loading"
        indeterminate
        min-width="300"
        class="mb-0"
      />
    </v-list>
    <v-divider />
    <v-card-actions class="justify-center pa-2">
      <v-btn
        color="primary"
        @click="close()"
      >
        Cancel
      </v-btn>
      <v-spacer />
      <v-btn
        color="success"
        :disabled="is_loading"
        @click="setHighestInterface()"
      >
        Apply
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import ethernet from '@/store/ethernet'
import { EthernetInterface } from '@/types/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(ethernet_service)

export default Vue.extend({
  name: 'NetworkInterfacePriorityMenu',
  data() {
    return {
      interfaces: [] as EthernetInterface[],
    }
  },
  computed: {
    is_loading(): boolean {
      return this.interfaces.isEmpty()
    },
  },
  async mounted() {
    await this.fetchAvailableInterfaces()
  },
  methods: {
    close() {
      this.$emit('close')
    },
    order(index: number): string {
      // Based over: https://stackoverflow.com/a/39466341
      return `${index}${['st', 'nd', 'rd'][((index + 90) % 100 - 10) % 10 - 1] || 'th'}`
    },
    async setHighestInterface(): Promise<void> {
      this.is_loading = true
      const interface_priority = this.interfaces.map((inter) => ({ name: inter.name }))
      await back_axios({
        method: 'post',
        url: `${ethernet.API_URL}/set_interfaces_priority`,
        timeout: 10000,
        data: interface_priority,
      })
        .catch((error) => {
          const message = `Could not increase the priority for interface '${interface_priority}', ${error}.`
          notifier.pushError('INCREASE_NETWORK_INTERFACE_METRIC_FAIL', message)
        })
        .then(() => {
          notifier.pushSuccess(
            'INCREASE_NETWORK_INTERFACE_METRIC_SUCCESS',
            'Interfaces priorities successfully updated!',
            true,
          )
          this.close()
        })
      await this.fetchAvailableInterfaces()
      this.is_loading = false
    },
    async fetchAvailableInterfaces(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${ethernet.API_URL}/interfaces`,
        timeout: 5000,
      })
        .then((response) => {
          const interfaces = response.data as EthernetInterface[]
          interfaces.sort((a, b) => {
            if (!a.info) return -1
            if (!b.info) return 1
            return a.info.priority - b.info.priority
          })
          this.interfaces = interfaces
        })
        .catch((error) => {
          ethernet.setInterfaces([])
          notifier.pushBackError('ETHERNET_AVAILABLE_INTERFACES_FETCH_FAIL', error)
        })
    },
  },
})
</script>
