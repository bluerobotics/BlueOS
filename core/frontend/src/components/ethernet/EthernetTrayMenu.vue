<template>
  <v-menu
    :close-on-content-click="false"
    nudge-left="400"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
          class="px-1"
          color="white"
        >
          mdi-connection
        </v-icon>
      </v-card>
    </template>
    <ethernet-manager />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import EthernetManager from './EthernetManager.vue'

export default Vue.extend({
  name: 'EthernetTrayMenu',
  components: {
    EthernetManager,
  },
})
</script>

<style>
</style>
