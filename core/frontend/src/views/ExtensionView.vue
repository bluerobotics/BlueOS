<template>
  <BrIframe
    v-if="detected_port"
    :source="service_path"
    :class="fullpage ? 'fullpage' : ''"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import BrIframe from '@/components/utils/BrIframe.vue'
import services_scanner from '@/store/servicesScanner'
import { Service } from '@/types/helper'

export default Vue.extend({
  name: 'ExtensionView',
  components: {
    BrIframe,
  },
  data() {
    return {
      detected_port: undefined as number | undefined,
      cache_busting_time: Date.now(),
    }
  },
  computed: {
    fullpage(): boolean {
      return this.$route.query.full_page === 'true'
    },
    service(): Service | undefined {
      return services_scanner.services.filter(
        (service) => service?.metadata?.sanitized_name === this.$route.params.name,
      )[0] ?? undefined
    },
    port(): number {
      return this.service?.port ?? 80
    },
    service_path(): string {
      return `${window.location.protocol}//${window.location.hostname}:${this.detected_port}`
      + `?time=${this.cache_busting_time}`
    },
    service_name(): string {
      return this.service?.metadata?.name ?? 'BlueOS Extension'
    },
  },
  watch: {
    port(new_value) {
      if (new_value !== undefined) {
        this.detected_port = new_value
      }
    },
    service_name(new_value) {
      document.title = new_value
    },
  },
  mounted() {
    if (this.port !== undefined) {
      this.detected_port = this.port
    }
  },
})
</script>

<style>
.fullpage {
  position:absolute; left: 0; right: 0; bottom: 0; top: 0px;
}
</style>
