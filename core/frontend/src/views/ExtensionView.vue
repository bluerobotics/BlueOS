<template>
  <BrIframe
    v-if="detected_port"
    :source="service_path"
    :class="fullpage ? 'fullpage' : ''"
  />
  <SpinningLogo v-else-if="detected_port === undefined" size="15%" />
  <page-not-found v-else />
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import BrIframe from '@/components/utils/BrIframe.vue'
import helper from '@/store/helper'
import { Service } from '@/types/helper'

import PageNotFound from './PageNotFound.vue'

export default Vue.extend({
  name: 'ExtensionView',
  components: {
    BrIframe,
    PageNotFound,
    SpinningLogo,
  },
  data() {
    return {
      detected_port: undefined as number | undefined,
      cache_busting_time: Date.now(),
      remaining_path: '',
    }
  },
  computed: {
    fullpage(): boolean {
      return this.$route.query.full_page === 'true'
    },
    service(): Service | undefined {
      return helper.services.filter(
        (service) => service?.metadata?.sanitized_name === this.$route.params.name,
      )[0] ?? undefined
    },
    port(): number | undefined | null {
      if (helper.services.length === 0) {
        return undefined
      }
      return this.service?.port ?? null
    },
    supports_v2(): boolean {
      return this.service?.metadata?.works_in_relative_paths ?? false
    },
    service_path(): string {
      if (this.supports_v2) {
        return `/extensionv2/${this.$route.params.name}`
      }
      return `${window.location.protocol}//${window.location.hostname}:${this.detected_port}`
      + `/${this.remaining_path ?? ''}`
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
    if (this.port !== undefined && this.port !== null) {
      this.detected_port = this.port
    }
    // eslint-disable-next-line
    this.remaining_path = this.$route.params.pathMatch
  },
})
</script>

<style>
.fullpage {
  position:absolute; left: 0; right: 0; bottom: 0; top: 0;
}
</style>
