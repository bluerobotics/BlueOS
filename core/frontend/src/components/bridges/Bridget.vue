<template>
  <v-card
    width="500"
    elevation="0"
    class="mx-auto my-6"
  >
    <v-list
      v-if="are_bridges_available && !updating_bridges"
      dense
    >
      <template v-for="(bridge, index) in available_bridges">
        <v-divider
          v-if="index!==0"
          :key="index"
        />
        <v-list-item
          :key="index"
          class="pa-0"
        >
          <bridge-card :bridge="bridge" />
        </v-list-item>
      </template>
    </v-list>

    <v-container v-else-if="updating_bridges">
      <spinning-logo size="30%" />
    </v-container>
    <v-container
      v-else
      class="text-center"
    >
      <p class="text-h6">
        No bridges available.
      </p>
      <p class="text-subtitle-1">
        Remember that for the time, bridges are not persistent along system reboots, so
        if you have restarted your system you need to re-create your bridges.
      </p>
    </v-container>

    <v-fab-transition>
      <v-btn
        :key="'create_button'"
        :color="'blue'"
        fab
        large
        dark
        fixed
        bottom
        right
        class="v-btn--example"
        @click="openCreationDialog"
      >
        <v-icon>mdi-plus</v-icon>
      </v-btn>
    </v-fab-transition>

    <creation-dialog
      v-model="show_creation_dialog"
    />
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import bridget from '@/store/bridget'
import { Bridge } from '@/types/bridges'

import SpinningLogo from '../common/SpinningLogo.vue'
import BridgeCard from './BridgeCard.vue'
import CreationDialog from './BridgeCreationDialog.vue'

export default Vue.extend({
  name: 'Bridget',
  components: {
    BridgeCard,
    SpinningLogo,
    CreationDialog,
  },
  data() {
    return {
      show_creation_dialog: false,
    }
  },
  computed: {
    updating_bridges(): boolean {
      return bridget.updating_bridges
    },
    available_bridges(): Bridge[] {
      return bridget.available_bridges
    },
    are_bridges_available(): boolean {
      return this.available_bridges.length !== 0
    },
  },
  methods: {
    openCreationDialog(): void {
      this.show_creation_dialog = true
    },
  },
})
</script>
