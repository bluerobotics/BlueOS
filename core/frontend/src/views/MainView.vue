<template>
  <v-container>
    <v-bottom-sheet
      :value="true"
      inset
    >
      <v-card>
        <v-card-title>Mavlink connection change</v-card-title>
        <v-card-text>
          New Companion doesn't provide a fixed UDP Client endpoint on 192.168.2.1 anymore. For new
          connections Companion now provides an UDP Server locally on port 14550.

          For connecting QGroundControl, for example, please go to Comm Links and create an
          UDP endpoint pointing to companion.local or Companion's IP address (e.g.:192.168.2.2), on port 14550.
          <v-card-text />
        </v-card-text>
      </v-card>
    </v-bottom-sheet>
    <available-services-table />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import AvailableServicesTable from '@/components/scanner/availableServicesTable.vue'

export default Vue.extend({
  name: 'Main',
  components: {
    AvailableServicesTable,
  },
})
</script>
