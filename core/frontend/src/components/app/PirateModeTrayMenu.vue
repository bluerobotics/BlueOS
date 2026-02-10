<template>
  <v-menu
    v-model="show_menu"
    :close-on-content-click="false"
    nudge-left="200"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        id="pirate-mode-tray-menu-button"
        class="px-1"
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
          v-tooltip="pirate_mode_tooltip"
          color="white"
        >
          {{ settings.is_pirate_mode ? 'mdi-skull-crossbones' : 'mdi-robot-happy' }}
        </v-icon>
      </v-card>
    </template>
    <pirate-mode-menu
      @pirateModeChanged="showMenu(false)"
    />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'

import PirateModeMenu from './PirateModeMenu.vue'

export default Vue.extend({
  name: 'PirateModeTrayMenu',
  components: {
    PirateModeMenu,
  },
  data: () => ({
    show_menu: false,
    settings,
  }),
  computed: {
    pirate_mode_tooltip(): string {
      return `Pirate Mode ${settings.is_pirate_mode ? 'enabled' : 'disabled'}. Click to change.`
    },
  },
  methods: {
    showMenu(show: boolean): void {
      this.show_menu = show
    },
  },
})
</script>
