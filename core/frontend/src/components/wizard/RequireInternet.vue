<template>
  <div class="d-flex justify-center align-center">
    <v-card elevation="0">
      <v-stepper vertical elevation="0">
        <v-stepper-step
          step="1"
          :color="icon_color"
          :complete-icon="icon"
          :complete="true"
          active
          class="step-label"
        >
          {{ text }}
        </v-stepper-step>
      </v-stepper>
      <WifiManager
        v-if="!is_online && !checking"
        :show-top-bar="false"
        @current-network="(net) => connected = net != null"
      />
    </v-card>
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
      checking: true,
      re_checking: false,
      is_online: false,
      timeout: 0,
    }
  },
  computed: {
    icon_color() {
      if (this.checking || this.re_checking) {
        return 'warning'
      }
      return this.is_online ? 'success' : 'error'
    },
    icon() {
      if (this.checking || this.re_checking) {
        return 'mdi-loading mdi-spin'
      }
      return this.is_online ? 'mdi-check' : 'mdi-close'
    },
    text() {
      if (this.checking) {
        return 'Checking Internet Connection...'
      }
      return this.is_online ? 'Internet Connection Established' : 'No Internet Connection, please connect to a network'
    },
  },
  watch: {
    connected() {
      if (this.connected) {
        this.checking = true
        this.checkInternet()
      }
    },
    is_online() {
      if (this.is_online) {
        this.$emit('online')
      }
    },
  },
  async mounted() {
    this.checkInternet()
  },
  methods: {
    checkInternet() {
      this.re_checking = true
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
          this.checking = false
          this.re_checking = false
        })
        .catch((error) => {
          if (error === backend_offline_error) { return }
          this.is_online = false
        })
        .finally(() => {
          if (!this.is_online) {
            this.timeout = setTimeout(() => {
              this.checkInternet()
            }, 5000)
          } else {
            clearInterval(this.timeout)
            this.timeout = setTimeout(() => {
              this.$emit('next')
            }, 1000)
          }
        })
    },
  },
})
</script>
