<template>
  <BrIframe
    :source="service_path"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import BrIframe from '@/components/utils/BrIframe.vue'

export default Vue.extend({
  name: 'TerminalView',
  components: {
    BrIframe,
  },
  data() {
    return {
      service_path: '/terminal/',
    }
  },
})
</script>
