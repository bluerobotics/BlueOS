<template>
  <v-container>
    <nmea-injector />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import NMEAInjector from '@/components/nmea-injector/NMEAInjector.vue'

export default Vue.extend({
  name: 'NMEAInjectorView',
  components: {
    'nmea-injector': NMEAInjector,
  },
})
</script>
