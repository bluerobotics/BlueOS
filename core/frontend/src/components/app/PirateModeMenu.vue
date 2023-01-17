<template>
  <v-card
    class="d-flex flex-column align-center pa-3"
    outlined
    width="300"
  >
    <v-alert
      v-if="!settings.is_pirate_mode"
      colored-border
      type="info"
      icon="mdi-skull-crossbones"
      elevation="2"
      text
    >
      Use Pirate Mode to show hidden pages and advanced settings.
      Pirate powers should be used with care.
    </v-alert>
    <v-btn
      @click="togglePirateMode"
    >
      {{ settings.is_pirate_mode ? "Disable Pirate Mode" : "Enable Pirate Mode" }}
    </v-btn>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'

export default Vue.extend({
  name: 'PirateModeMenu',
  data() {
    return {
      settings,
    }
  },
  methods: {
    togglePirateMode(): void {
      this.$emit('pirateModeChanged', settings.is_pirate_mode)

      // Wait for menu to close before changing pirate mode,
      // otherwise the menu will change before closing it
      setTimeout(() => {
        settings.is_pirate_mode = !settings.is_pirate_mode
      }, 300)
    },
  },
})
</script>
