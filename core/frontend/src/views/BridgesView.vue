<template>
  <v-container>
    <bridget />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import Bridget from '@/components/bridges/Bridget.vue'

export default Vue.extend({
  name: 'BridgesView',
  components: {
    Bridget,
  },
})
</script>
