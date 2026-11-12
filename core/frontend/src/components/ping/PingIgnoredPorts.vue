<template>
  <v-card
    class="ma-7"
    max-width="700"
    outlined
  >
    <v-card-title>{{ t`Ignored serial ports` }}</v-card-title>
    <v-card-subtitle>
      <!-- eslint-disable-next-line max-len -->
      {{ t`Selected ports are not probed for Ping devices. A Ping that was already detected keeps running until it is unplugged or BlueOS reboots.` }}
    </v-card-subtitle>
    <v-list dense>
      <v-list-item-group
        v-model="selected"
        multiple
      >
        <v-list-item
          v-for="port in ports"
          :key="port.path"
          :value="port.path"
        >
          <template #default="{ active }">
            <v-list-item-action>
              <v-checkbox :input-value="active" />
            </v-list-item-action>
            <v-list-item-content>
              <v-list-item-title class="text-wrap">
                {{ port.path }}
              </v-list-item-title>
              <v-list-item-subtitle v-if="port.device !== port.path">
                {{ port.device ?? t`Not connected` }}
              </v-list-item-subtitle>
            </v-list-item-content>
            <v-list-item-action v-if="port.device">
              <device-path-helper :device="port.device" />
            </v-list-item-action>
          </template>
        </v-list-item>
      </v-list-item-group>
      <v-list-item v-if="ports.length === 0">
        {{ t`No serial ports available` }}
      </v-list-item>
    </v-list>
    <v-card-actions>
      <v-spacer />
      <v-btn
        color="primary"
        :disabled="!changed"
        :loading="saving"
        @click="save"
      >
        {{ t`Save` }}
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import { t } from 'ttag'
import Vue from 'vue'

import DevicePathHelper from '@/components/common/DevicePathHelper.vue'
import Notifier from '@/libs/notifier'
import system_information from '@/store/system-information'
import { ping_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(ping_service)

interface IgnoredPort {
  path: string
  device: string | null
}

export default Vue.extend({
  name: 'PingIgnoredPorts',
  components: {
    DevicePathHelper,
  },
  data() {
    return {
      saved: [] as string[],
      selected: [] as string[],
      saving: false,
    }
  },
  computed: {
    ports(): IgnoredPort[] {
      const connected = (system_information.serial?.ports ?? []).map((port) => {
        const udev = port.udev_properties as Record<string, string> | null
        const by_id = udev?.DEVLINKS?.split(' ').find((link) => link.startsWith('/dev/serial/by-id/'))
        const names = [by_id, port.by_path, port.name].filter((name): name is string => Boolean(name))
        return { path: this.saved.find((entry) => names.includes(entry)) ?? names[0], device: port.name }
      })
      const missing = this.saved.filter((entry) => !connected.some((port) => port.path === entry))
      return [...connected, ...missing.map((path) => ({ path, device: null }))]
    },
    changed(): boolean {
      return [...this.selected].sort().join() !== [...this.saved].sort().join()
    },
  },
  mounted() {
    this.fetch()
  },
  methods: {
    async fetch(): Promise<void> {
      await back_axios({ method: 'get', url: '/ping/v1.0/ignored_ports', timeout: 10000 })
        .then((response) => {
          this.saved = response.data
          this.selected = [...this.saved]
        })
        .catch((error) => notifier.pushBackError('PING_IGNORED_PORTS_FETCH_FAIL', error))
    },
    async save(): Promise<void> {
      this.saving = true
      await back_axios({
        method: 'post', url: '/ping/v1.0/ignored_ports', data: this.selected, timeout: 10000,
      })
        .then(() => {
          this.saved = [...this.selected]
          notifier.pushSuccess('PING_IGNORED_PORTS_SAVE_SUCCESS', t`Ignored serial ports saved.`, true)
        })
        .catch((error) => notifier.pushBackError('PING_IGNORED_PORTS_SAVE_FAIL', error, true))
        .finally(() => { this.saving = false })
    },
  },
})
</script>
