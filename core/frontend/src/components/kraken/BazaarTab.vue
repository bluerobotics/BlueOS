<template>
  <div>
    <v-card v-if="show_info_card" class="pa-5">
      <v-container
        class="text-center fill-height d-flex flex-column justify-center align-center mt-5"
      >
        <SpinningLogo
          v-if="bazaar_url_loading"
          size="200"
          subtitle="Fetching Bazaar!"
        />
        <div v-else-if="major_tom_not_configured" class="text-center">
          <v-icon
            class="mt-16"
            color="red"
            size="100"
          >
            mdi-cloud-off-outline
          </v-icon>
          <v-card-title class="mb-5">
            Major Tom is not configured. <br />
            Use the cloud icon in the top right corner to configure Major Tom.
          </v-card-title>
          <v-card-subtitle>
            If the cloud icon is not visible, make sure Major Tom is enabled in installed extensions.
          </v-card-subtitle>
        </div>
        <div v-else>
          <v-icon
            class="mt-16 mb-5"
            color="red"
            size="100"
          >
            {{ internet_offline ? 'mdi-web-off' : 'mdi-alert-octagon' }}
          </v-icon>
          <v-card-title class="mb-5">
            {{ internet_offline ? 'Vehicle is not connected to the internet.' : 'Failed to fetch extension manifest.' }}
          </v-card-title>
        </div>
      </v-container>
    </v-card>
    <v-card v-else class="pa-2" style="height: 85vh;">
      <BrIframe
        v-if="!is_bazaar_invalid"
        :source="bazaar_url"
      />
    </v-card>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import BrIframe from '@/components/utils/BrIframe.vue'
import { OneMoreTime } from '@/one-more-time'
import bag from '@/store/bag'
import helper from '@/store/helper'

export default Vue.extend({
  name: 'BazaarTab',
  components: {
    BrIframe,
    SpinningLogo,
  },
  data() {
    return {
      bazaar_url: undefined as string | undefined,
      bazaar_url_error: undefined as string | undefined,
      bazaar_url_loading: false,
      check_bazaar_url_task: new OneMoreTime({ delay: 600000, disposeWith: this }),
    }
  },
  computed: {
    is_bazaar_invalid(): boolean {
      return this.bazaar_url_loading || this.bazaar_url_error !== undefined
    },
    internet_offline(): boolean {
      return !helper.has_internet
    },
    major_tom_not_configured(): boolean {
      return this.bazaar_url === undefined && !this.internet_offline
    },
    show_info_card(): boolean {
      return this.is_bazaar_invalid || this.internet_offline || this.major_tom_not_configured
    },
  },
  async mounted() {
    this.check_bazaar_url_task.setAction(this.fetchBazaarURL)
  },
  methods: {
    async fetchBazaarURL(): Promise<void> {
      // We should only show loading process to user if no URL is available
      if (this.bazaar_url === undefined) {
        this.bazaar_url_loading = true
      }

      // Small delay to prevent flickering
      await new Promise((resolve) => { setTimeout(resolve, 800) })

      try {
        const tomData = await bag.getData('major_tom')
        const url = tomData?.inventory_url ? String(tomData.inventory_url) : undefined

        if (this.bazaar_url !== url) {
          this.bazaar_url = url
        }
      } catch (error) {
        this.bazaar_url_error = String(error)
      } finally {
        this.bazaar_url_loading = false
      }

      // If we still don't have a URL, we should try again faster than usual
      if (this.bazaar_url === undefined) {
        this.check_bazaar_url_task.setDelay(10000)
      } else {
        this.check_bazaar_url_task.setDelay(600000)
      }
    },
  },
})
</script>
