<template>
  <v-card class="pa-2 mx-auto" min-width="100%">
    <v-card-title class="text-md-center" max-width="30">
      Host DNS nameservers
    </v-card-title>
    <v-card-text style="max-width: 30rem;">
      <v-icon class="pr-2">
        mdi-information
      </v-icon>
      These nameservers are fetched from and applied to the host resolv configuration (<i>/etc/resolv.conf</i>),
      which are synchronized with the container's resolv configuration.
    </v-card-text>
    <v-form
      ref="host_nameservers_form"
      v-model="valid_host_nameservers"
      lazy-validation
    >
      <div
        v-if="host_nameservers.length > 0"
      >
        <v-checkbox
          v-model="is_locked"
          v-tooltip="'Use this to prevent other Linux services (like dnsmasq or dhcpcd)'
            + ' from automatically changing the nameservers'"
          :disabled="updating_host_nameservers"
          label="Lock DNS nameservers configuration"
        />
        <v-card
          v-for="(nameserver, index) in host_nameservers"
          :key="index"
          class="pl-3 ma-4 pa-1 d-flex align-center justify-space-between"
        >
          <v-text-field
            ref="dnsEntry"
            v-model="host_nameservers[index]"
            :label="`Nameserver #${index + 1}`"
            :rules="[is_valid_ip_input]"
          />
          <v-spacer />
          <v-btn
            v-if="host_nameservers.length > 1"
            v-tooltip="'Remove this nameserver'"
            color="fail"
            rounded
            small
            icon
            @click="remove_dns_entry(index)"
          >
            <v-icon>mdi-close-thick</v-icon>
          </v-btn>
        </v-card>
      </div>
      <v-card-text v-else-if="is_loading_host_nameservers">
        Fetching Host DNS nameservers...
      </v-card-text>
      <v-alert v-else-if="!error" type="warning" style="max-width: 30rem;">
        No DNS nameservers found on host's resolv.conf configuration.
        At least one nameserver is recommended for the system have access to the internet.
        Click on "ADD DNS" below to add a new nameserver.
      </v-alert>
    </v-form>
    <v-progress-linear
      v-if="is_loading_host_nameservers"
      indeterminate
      min-width="300"
      class="mb-0"
    />
    <v-divider />
    <v-alert v-if="error" type="error" style="max-width: 30rem;">
      {{ error }}
    </v-alert>
    <v-card-actions class="justify-center pa-4">
      <v-btn
        v-tooltip="'Add one more DNS entry'"
        color="primary"
        :disabled="is_loading_host_nameservers"
        @click="add_dns_entry"
      >
        ADD DNS
      </v-btn>
      <v-btn
        v-if="!error"
        color="success"
        :disabled="is_loading_host_nameservers || !valid_host_nameservers"
        @click="applyHostDns()"
      >
        APPLY
      </v-btn>
      <v-btn
        v-else
        v-tooltip="'Try to fetch DNS namservers from the host'"
        color="success"
        :disabled="is_loading_host_nameservers || !valid_host_nameservers"
        @click="fetchHostDns()"
      >
        TRY AGAIN
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import ethernet from '@/store/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import { isIpAddress } from '@/utils/pattern_validators'

const notifier = new Notifier(ethernet_service)

export default Vue.extend({
  name: 'DnsConfigurationMenu',
  data() {
    return {
      valid_host_nameservers: false,
      host_nameservers: [] as string[],
      updating_host_nameservers: true,
      is_locked: false,
      error: null as string | null,
    }
  },
  computed: {
    is_loading_host_nameservers(): boolean {
      return this.updating_host_nameservers
    },
  },
  async mounted() {
    await this.fetchHostDns()
  },
  methods: {
    is_valid_ip_input(input: string): (true | string) {
      return isIpAddress(input) ? true : 'Invalid_blueos_nameservers IP address.'
    },
    add_dns_entry() {
      this.host_nameservers.push('')

      // Focus on the added element
      this.$nextTick(() => {
        const dnsEntries = this.$refs.dnsEntry as HTMLInputElement[]
        if (!dnsEntries) {
          return
        }

        dnsEntries.last()?.focus()
      })
    },
    remove_dns_entry(index: number) {
      this.host_nameservers.splice(index, 1)
    },
    close() {
      this.$emit('close')
    },
    async fetchHostDns(): Promise<void> {
      this.updating_host_nameservers = true
      this.error = null

      await back_axios({
        method: 'get',
        url: `${ethernet.API_URL}/host_dns`,
        timeout: 15000,
      })
        .then((response) => {
          const { data } = response

          this.host_nameservers = data.nameservers as string[]
          this.is_locked = data.lock as boolean
        })
        .catch((error) => {
          ethernet.setInterfaces([])
          notifier.pushBackError('HOST_DNS_FETCH_FAIL', error)
          this.error = 'Failed to fetch host DNS configuration, try again later'
        })

      this.updating_host_nameservers = false
    },
    async applyHostDns(): Promise<void> {
      this.updating_host_nameservers = true
      this.error = null

      await back_axios({
        method: 'post',
        url: `${ethernet.API_URL}/host_dns`,
        timeout: 15000,
        data: {
          nameservers: this.host_nameservers,
          lock: this.is_locked,
        },
      })
        .catch((error) => {
          notifier.pushError('APPLY_HOST_DNS_FAIL', error)
          this.error = 'Failed to apply changes, try again later'
        })
        .then(() => {
          notifier.pushSuccess(
            'APPLY_HOST_DNS_SUCCESS',
            'Host DNS nameservers updated successfully!',
            true,
          )
          this.close()
        })

      this.updating_host_nameservers = false
    },
  },
})
</script>
