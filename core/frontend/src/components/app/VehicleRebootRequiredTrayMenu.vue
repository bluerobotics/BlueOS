<template>
  <v-menu
    v-if="autopilot_data.reboot_required"
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
          class="blinking"
        >
          mdi-restart-alert
        </v-icon>
      </v-card>
    </template>
    <vehicle-reboot-menu
      @vehicleRebootCalled="showMenu(false)"
    />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'

import VehicleRebootMenu from './VehicleRebootMenu.vue'

export default Vue.extend({
  name: 'VehicleRebootRequiredTrayMenu',
  components: {
    VehicleRebootMenu,
  },
  data: () => ({
    autopilot_data,
    show_menu: false,
  }),
  methods: {
    showMenu(show: boolean): void {
      this.show_menu = show
    },
  },
})
</script>

<style scoped>
  .blinking {
    animation-name: blinking;
    animation-duration: 2s;
    animation-iteration-count: infinite;
  }

  @keyframes blinking {
    100% {color: red;}
    75% {color: yellow;}
    50% {color: red;}
    25% {color: yellow;}
    0% {color: red;}
  }

  .white-shadow {
    text-shadow: 0 0 3px #FFF;
  }
</style>
