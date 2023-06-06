<template>
  <div>
    <v-card
      color="primary"
      dark
      class="mb-5"
    >
      <v-card-text
        class="d-flex flex-column align-center subtitle font-weight-medium"
      >
        {{ status }}
        <v-progress-linear
          v-if="connected"
          indeterminate
          color="white"
          class="mb-0"
        />
      </v-card-text>
    </v-card>
    <WifiManager
      :show-top-bar="false"
      @current-network="(net) => connected = net != null"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import WifiManager from '@/components/wifi/WifiManager.vue'
import back_axios, { backend_offline_error } from '@/utils/api'

type CheckSiteStatus = {
  site: string;
  online: boolean;
  error: string | null;
};

type SiteStatus = Record<string, CheckSiteStatus>

export default Vue.extend({
  name: 'RequireInternet',
  components: {
    WifiManager,
  },
  data() {
    return {
      connected: false,
      is_online: false,
    }
  },
  computed: {
    status(): string {
      if (this.connected) {
        return 'Internet is available'
      }

      return 'Please connect to a wifi network with internet'
    },
  },
  async mounted() {
    this.checkInternet()
  },
  methods: {
    checkInternet() {
      back_axios({
        method: 'get',
        url: '/helper/latest/check_internet_access',
        timeout: 10000,
      })
        .then((response) => {
          // eslint-disable-next-line prefer-destructuring
          const data: SiteStatus = response.data
          this.is_online = !Object.values(data)
            .filter((item) => item.online)
            .isEmpty()
          if (this.is_online) {
            this.$emit('next')
          }
        })
        .catch((error) => {
          if (error === backend_offline_error) { return }
          this.is_online = false
        })
        .finally(() => {
          if (!this.is_online) {
            this.checkInternet()
          }
        })
    },
  },
})
</script>
