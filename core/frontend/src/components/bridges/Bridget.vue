<template>
  <v-card
    width="700"
    elevation="0"
    class="mb-12 pa-6 bridges-list"
  >
    <v-list
      v-if="are_bridges_available && !updating_bridges"
      style="background-color: transparent"
      dense
    >
      <template v-for="(info, index) in available_bridges">
        <v-divider
          v-if="index !== 0"
          :key="`divider-${index}`"
        />
        <v-list-item
          :key="index"
          class="pa-0"
        >
          <bridge-card :bridge-serial-info="info" />
        </v-list-item>
      </template>
    </v-list>

    <v-container v-else-if="updating_bridges">
      <spinning-logo
        size="30%"
        subtitle="Fetching available bridges..."
      />
    </v-container>
    <v-container
      v-else
      class="text-center"
    >
      <p class="text-h6">
        No bridges available. You can add a serial to UDP bridge by clicking the + symbol in the corner.
      </p>
    </v-container>

    <v-fab-transition>
      <v-btn
        :key="'create_button'"
        color="primary"
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

import { OneMoreTime } from '@/one-more-time'
import bridget from '@/store/bridget'
import system_information from '@/store/system-information'
import { BridgeWithSerialInfo } from '@/types/bridges'
import { SerialPortInfo } from '@/types/system-information/serial'

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
      fetch_serial_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
    }
  },
  computed: {
    updating_bridges(): boolean {
      return bridget.updating_bridges
    },
    available_bridges(): BridgeWithSerialInfo[] {
      const system_serial_ports: SerialPortInfo[] | undefined = system_information.serial?.ports
      return bridget.available_bridges.map((bridge) => ({
        bridge,
        serial_info: system_serial_ports?.find(
          (serial_info) => (serial_info.by_path ?? serial_info.name) === bridge.serial_path,
        ),
      }))
    },
    are_bridges_available(): boolean {
      return !this.available_bridges.isEmpty()
    },
  },
  mounted() {
    this.fetch_serial_task.setAction(system_information.fetchSerial)
    bridget.registerObject(this)
  },
  methods: {
    openCreationDialog(): void {
      this.show_creation_dialog = true
    },
  },
})
</script>

<style scoped>
.bridges-list {
  background-color: transparent;
  max-width: 70%;
  margin: auto;
}
</style>
