<template>
  <BrIframe
    :source="full_path"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import BrIframe from '@/components/utils/BrIframe.vue'
import { Route } from 'vue-router';

export default Vue.extend({
  name: 'FileBrowserView',
  components: {
    BrIframe,
  },
  data() {
    return {
      service_path: '/file-browser/',
    }
  },
  computed: {
    route(): Route {
      return (this as any).$route as Route
    },
    full_path() : string {
      return `${this.service_path}${this.route.params.path ?? ''}`
    },
  },
})
</script>
