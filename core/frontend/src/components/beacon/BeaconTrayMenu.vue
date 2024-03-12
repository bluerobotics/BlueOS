<template>
  <v-menu
    v-if="should_warn_user"
    :close-on-content-click="false"
    nudge-left="150"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
          class="px-1 white-shadow"
          :v-tooltip="tooltip_text"
          :color="should_warn_user ? 'yellow' : 'white'"
        >
          mdi-ethernet-cable
        </v-icon>
      </v-card>
    </template>

    <v-card
      elevation="1"
      width="300"
    >
      <v-container>
        <div class="justify-center">
          It looks like you are reaching BlueOS via its wi-fi network. This can result in degraded performance.
          <span
            v-if="available_wired_domain()"
            class="mt-3"
            style="display: block;"
          >
            A wired connection is available:
            <v-btn
              small
              :href="`http://${available_wired_domain()}.local`"
            >
              Switch to {{ available_wired_domain() }}.local
            </v-btn>
          </span>
        </div>
      </v-container>
    </v-card>
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import beacon from '@/store/beacon'
import { Domain, InterfaceType } from '@/types/beacon'
import { Dictionary } from '@/types/common'
import back_axios from '@/utils/api'

export default Vue.extend({
  name: 'BeaconTrayMenu',
  data() {
    return {
      probe_timer: 0,
      domains: {} as Dictionary<boolean>,
    }
  },
  computed: {
    wired_interface_domains(): Domain[] {
      return beacon.available_domains.filter(
        (entry) => entry.interface_type === InterfaceType.WIRED || entry.interface_type === InterfaceType.USB,
      )
    },
    wireless_interface_domains(): Domain[] {
      return beacon.available_domains.filter(
        (entry) => entry.interface_type === InterfaceType.WIFI || entry.interface_type === InterfaceType.HOTSPOT,
      )
    },
    is_connected_to_wired(): boolean {
      return this.wired_interface_domains.some((domain) => domain.ip === beacon.nginx_ip_address)
    },
    is_connected_to_wifi(): boolean {
      const is_on_wifi = this.wireless_interface_domains.some((domain) => domain.ip === beacon.nginx_ip_address)

      if (is_on_wifi && this.is_connected_to_wired) {
        console.debug('Unexpected behavior. There are both Wired and Wireless interfaces sharing the same IP address.')
      }

      return is_on_wifi && !this.is_connected_to_wired
    },
    is_connected_to_unknown_interface(): boolean {
      return !this.is_connected_to_wifi && !this.is_connected_to_wired
    },
    should_warn_user(): boolean {
      return this.is_connected_to_wifi || this.is_connected_to_unknown_interface
    },
    tooltip_text(): string {
      if (this.is_connected_to_wifi) {
        return 'Connected through a wireless connection, expect degraded performance'
      }
      if (this.is_connected_to_wired) {
        return 'Connected through a wired connection'
      }

      return 'It looks like you are reaching BlueOS using a complex network. '
        + 'Degraded performance can happen in this case.'
    },
  },
  mounted() {
    beacon.registerBeaconListener(this)
    this.probeDomains()
    this.probe_timer = setInterval(() => {
      this.probeDomains()
    }, 20000)
  },
  beforeDestroy() {
    clearInterval(this.probe_timer)
  },
  methods: {
    probeDomains() {
      // Probe beacon domains in an attempt to find a wired connection.
      if (!this.is_connected_to_wifi) {
        return
      }
      // GET errors cannot be suppressed in the console, so let's be transparent to the users about
      // why we are seeing them
      console.log('Trying to find a wired link to BlueOS...')
      for (const domain of this.wired_interface_domains) {
        back_axios({
          method: 'get',
          url: `http://${domain.ip}/status`,
          timeout: 1000,
        })
          .then(() => {
            this.domains[domain.hostname] = true
          })
          .catch(() => {
            this.domains[domain.hostname] = false
          })
      }
    },
    available_wired_domain(): string | null {
      for (const [domain, accessible] of Object.entries(this.domains)) {
        if (accessible) {
          return domain
        }
      }
      return null
    },
  },
})
</script>

<style>
.white-shadow {
  text-shadow: 0 0 3px #FFF;
}
</style>
