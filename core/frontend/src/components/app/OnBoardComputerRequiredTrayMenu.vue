<template>
  <v-menu
    v-if="commander.on_board_computer_reboot_required"
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
    <on-board-computer-reboot-menu
      @vehicleRebootCalled="showMenu(false)"
    />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import commander from '@/store/commander'

import OnBoardComputerRebootMenu from './OnBoardComputerRebootMenu.vue'

export default Vue.extend({
  name: 'OnBoardComputerRequiredTrayMenu',
  components: {
    OnBoardComputerRebootMenu,
  },
  data: () => ({
    commander,
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
