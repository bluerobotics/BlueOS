<template>
  <v-container>
    <available-services-table />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import AvailableServicesTable from '@/components/scanner/availableServicesTable.vue'

export default Vue.extend({
  name: 'AvailableServicesView',
  components: {
    AvailableServicesTable,
  },
})
</script>
