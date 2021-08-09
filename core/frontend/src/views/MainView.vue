<template>
  <v-container>
    <available-services-table />
  </v-container>
</template>

<script lang="ts">
import AvailableServicesTable from '@/components/scanner/availableServicesTable.vue'
import Vue from 'vue'

export default Vue.extend({
  name: 'Main',
  components: {
    AvailableServicesTable,
  },
})
</script>
