<template>
  <v-card class="pa-2 mx-auto" min-width="100%">
    <v-list>
      <v-card-subtitle class="text-md-center" max-width="30">
        Drag the network interfaces to move the highest priority to the top.<br>
        Applied changes require a <b>system reboot</b>.
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
          <v-tooltip bottom>
            <template #activator="{ on }">
              <v-icon
                class="pr-2"
                :color="internetStatusColor(element)"
                v-on="on"
              >
                {{ internetStatusIcon(element) }}
              </v-icon>
            </template>
            <span>
              {{ internetStatusText(element) }}
            </span>
          </v-tooltip>
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
import helper from '@/store/helper'
import { EthernetInterface } from '@/types/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(ethernet_service)

export default Vue.extend({
  name: 'NetworkInterfacePriorityMenu',
  data() {
    return {
      interfaces: [] as EthernetInterface[],
      internet_access: {} as Record<string, boolean | undefined>,
    }
  },
  computed: {
    is_loading(): boolean {
      return this.interfaces.isEmpty()
    },
  },
  watch: {
    interfaces: {
      handler(interfaces: EthernetInterface[]) {
        this.checkInterfacesInternet(interfaces)
      },
      immediate: true,
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
    internetStatusColor(iface: EthernetInterface): string {
      const status = this.internet_access[iface.name]
      if (status === undefined) return 'white'
      return status ? 'green' : 'red'
    },
    internetStatusIcon(iface: EthernetInterface): string {
      const status = this.internet_access[iface.name]
      if (status === undefined) return 'mdi-loading mdi-spin'
      return status ? 'mdi-web' : 'mdi-web-off'
    },
    internetStatusText(iface: EthernetInterface): string {
      const status = this.internet_access[iface.name]
      if (status === undefined) return 'Checking if this interface has internet access...'
      return status ? 'Online' : 'Offline'
    },
    async checkInterfaceInternet(host: string, iface: EthernetInterface): Promise<void> {
      const result = await helper.ping({ host, iface: iface.name })
      Vue.set(this.internet_access, iface.name, result)
    },
    async checkInterfacesInternet(interfaces: EthernetInterface[]): Promise<void> {
      if (!helper.has_internet) {
        this.internet_access = interfaces.reduce((acc, iface) => {
          acc[iface.name] = false
          return acc
        }, {} as Record<string, boolean | undefined>)
        return
      }

      const host = helper.reachable_hosts?.[0] ?? '1.1.1.1'
      await Promise.all(interfaces.map((iface) => this.checkInterfaceInternet(host, iface)))
    },
    async setHighestInterface(): Promise<void> {
      const interface_priorities = this.interfaces.map((inter) => ({ name: inter.name, priority: 0 }))
      interface_priorities.forEach((inter, index) => {
        inter.priority = index * 1000
      })
      this.interfaces = []
      await back_axios({
        method: 'post',
        url: `${ethernet.API_URL}/set_interfaces_priority`,
        timeout: 10000,
        data: interface_priorities,
      })
        .catch((error) => {
          const message = `Could not set network interface priorities: ${interface_priorities}, error: ${error}`
          notifier.pushError('INCREASE_NETWORK_INTERFACE_METRIC_FAIL', message)
        })
        .then(() => {
          notifier.pushSuccess(
            'INCREASE_NETWORK_INTERFACE_METRIC_SUCCESS',
            'Network interface priorities successfully updated!',
            true,
          )
          this.close()
        })
      await this.fetchAvailableInterfaces()
    },
    async fetchAvailableInterfaces(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${ethernet.API_URL}/interfaces`,
        // Necessary since the system can hang with dhclient timeouts
        timeout: 10000,
      })
        .then((response) => {
          const interfaces = response.data as EthernetInterface[]
          interfaces.sort((a, b) => {
            const priorityA = a.priority ?? Number.MAX_SAFE_INTEGER
            const priorityB = b.priority ?? Number.MAX_SAFE_INTEGER
            return priorityA - priorityB
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
