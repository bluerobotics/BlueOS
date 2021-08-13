<template>
  <v-menu
    :close-on-content-click="false"
    nudge-left="500"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        class="px-1"
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon color="white">
          mdi-wifi
        </v-icon>
      </v-card>
    </template>
    <wifi-manager />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import WifiManager from './WifiManager.vue'

export default Vue.extend({
  name: 'WifiTrayMenu',
  components: {
    WifiManager,
  },
})
</script>

<style>
</style>
