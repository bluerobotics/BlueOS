<template>
  <zenoh-inspector />
</template>

<script lang="ts">
import Vue from 'vue'

import ZenohInspector from '@/components/zenoh-inspector/ZenohInspector.vue'

export default Vue.extend({
  name: 'ZenohInspectorView',
  components: {
    'zenoh-inspector': ZenohInspector,
  },
})
</script>
