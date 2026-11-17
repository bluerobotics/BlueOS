<template>
  <v-card
    class="d-flex flex-column align-center pa-3"
    outlined
    width="350"
  >
    <v-alert
      type="info"
      icon="mdi-skull-crossbones"
      elevation="1"
      text
    >
      On-board computer reboot is necessary.
    </v-alert>
    <v-btn
      @click="rebootOnBoardComputer"
    >
      Reboot On-board Computer
    </v-btn>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import commander from '@/store/commander'

export default Vue.extend({
  name: 'OnBoardComputerRebootMenu',
  methods: {
    rebootOnBoardComputer() {
      commander.rebootOnBoardComputer()
    },
  },
})
</script>
