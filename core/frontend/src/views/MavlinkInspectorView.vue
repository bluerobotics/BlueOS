<template>
  <mavlink-inspector />
</template>

<script lang="ts">
import Vue from 'vue'

import MavlinkInspector from '@/components/mavlink-inspector/MavlinkInspector.vue'

export default Vue.extend({
  name: 'MavlinkInspectorView',
  components: {
    'mavlink-inspector': MavlinkInspector,
  },
})
</script>
