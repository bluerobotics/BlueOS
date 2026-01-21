<template>
  <div class="d-flex align-center">
    <wifi-updater v-if="!wifi_service_disabled" />

    <template v-if="has_multiple_interfaces">
      <wifi-interface-tray-menu
        v-for="iface in wifi_interfaces"
        :key="iface.name"
        :interface-name="iface.name"
        class="mr-1"
      />
    </template>

    <template v-else>
      <v-menu
        :close-on-content-click="false"
        nudge-left="500"
        nudge-bottom="25"
      >
        <template
          #activator="{ on, attrs }"
        >
          <v-card
            id="wifi-tray-menu-button"
            class="px-1"
            elevation="0"
            color="transparent"
            v-bind="attrs"
            v-on="on"
          >
            <v-icon
              v-tooltip="{
                content: wifi_service_disabled ? 'Wifi is disabled' : undefined,
                bottom: true,
                offset: 5,
              }"
              color="white"
            >
              {{ wifi_icon }}
            </v-icon>
          </v-card>
        </template>
        <wifi-manager v-if="!wifi_service_disabled" />
        <v-card
          v-else
          elevation="1"
          width="500"
        >
          <v-card-title class="text-subtitle-1 pa-4">
            Wifi is disabled via environment variable. <br>
            Re-enable it by removing "wifi" from <code>BLUEOS_DISABLE_SERVICES</code>
            in <code>/root/.config/bootstrap/startup.json</code>
          </v-card-title>
        </v-card>
      </v-menu>
    </template>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import commander from '@/store/commander'
import wifi from '@/store/wifi'
import { WifiInterface } from '@/types/wifi'
import { wifi_strenght_icon } from '@/utils/wifi'

import WifiInterfaceTrayMenu from './WifiInterfaceTrayMenu.vue'
import WifiManager from './WifiManager.vue'
import WifiUpdater from './WifiUpdater.vue'

export default Vue.extend({
  name: 'WifiTrayMenu',
  components: {
    WifiManager,
    WifiUpdater,
    WifiInterfaceTrayMenu,
  },
  data() {
    return {
      disabled_services: undefined as string[] | undefined,
    }
  },
  computed: {
    wifi_service_disabled(): boolean {
      return this.disabled_services?.includes('wifi') ?? false
    },
    wifi_interfaces(): WifiInterface[] {
      return wifi.wifi_interfaces
    },
    has_multiple_interfaces(): boolean {
      return this.wifi_interfaces.length > 0
    },
    wifi_icon(): string {
      if (this.wifi_service_disabled) {
        return 'mdi-wifi-cancel'
      }
      if (wifi.connectable_networks === null) {
        return 'mdi-wifi-sync'
      }
      if (wifi.current_network === null) {
        return 'mdi-wifi-off'
      }
      return wifi_strenght_icon(wifi.current_network.signal)
    },
  },
  mounted() {
    commander.getEnvironmentVariables().then((environment_variables) => {
      this.disabled_services = (environment_variables?.BLUEOS_DISABLE_SERVICES as string ?? '').split(',') as string[]
    })
  },
})
</script>

<style>
</style>
