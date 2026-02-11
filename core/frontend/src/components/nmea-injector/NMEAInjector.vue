<template>
  <v-card
    width="500"
    elevation="0"
    class="mx-auto my-6 injectors-list"
  >
    <v-card
      class="mx-auto my-6"
      width="500"
      elevation="1"
    >
      <v-card-text>
        <div class="text--primary">
          The NMEA Injector receives NMEA via UDP or TCP and transforms it
          into MAVLink data that is forwarded to the autopilot.
          It currently supports the sentences
          <!-- suppressing vue-no-html rule, as we create this html ourselves -->
          <!-- eslint-disable -->
          <span
            target="_blank"
            v-html="createLink('GPGGA')"
          />,
          <span
            target="_blank"
            v-html="createLink('GPRMC')"
          />,
          <span
            target="_blank"
            v-html="createLink('GPGLL')"
          />, and
          <!-- eslint-enable -->
          <a
            target="_blank"
            href="https://receiverhelp.trimble.com/alloy-gnss/en-us/NMEA-0183messages_GNS.html"
          >
            GPGNSS
          </a>
        </div>
      </v-card-text>
    </v-card>
    <v-list
      v-if="are_nmea_sockets_available && !updating_nmea_sockets"
      style="background-color: transparent"
      dense
    >
      <template v-for="(nmea_socket, index) in available_nmea_sockets">
        <v-divider
          v-if="index !== 0"
          :key="index"
        />
        <v-list-item
          :key="index"
          class="pa-0"
        >
          <nmea-socket-card :nmea-socket="nmea_socket" />
        </v-list-item>
      </template>
    </v-list>

    <v-container v-else-if="updating_nmea_sockets">
      <spinning-logo
        size="30%"
        subtitle="Fetching available NMEA sockets..."
      />
    </v-container>
    <v-container
      v-else
      class="text-center"
    >
      <p class="text-h6">
        No NMEA sockets available. You can add a connection by clicking the + symbol in the corner.
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
import nmea_injector from '@/store/nmea-injector'
import { NMEASocket } from '@/types/nmea-injector'

import SpinningLogo from '../common/SpinningLogo.vue'
import NMEASocketCard from './NMEASocketCard.vue'
import CreationDialog from './NMEASocketCreationDialog.vue'

export default Vue.extend({
  name: 'NMEAInjector',
  components: {
    SpinningLogo,
    CreationDialog,
    'nmea-socket-card': NMEASocketCard,
  },
  data() {
    return {
      show_creation_dialog: false,
      updating_nmea_sockets_debounced: false,
      fetch_nmea_sockets_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
    }
  },
  computed: {
    updating_nmea_sockets(): boolean {
      return nmea_injector.updating_nmea_sockets && this.updating_nmea_sockets_debounced
    },
    available_nmea_sockets(): NMEASocket[] {
      return nmea_injector.available_nmea_sockets
    },
    are_nmea_sockets_available(): boolean {
      return !this.available_nmea_sockets.isEmpty()
    },
  },
  mounted() {
    this.fetch_nmea_sockets_task.setAction(() => this.fetchAvailableNMEASockets())
  },
  methods: {
    async fetchAvailableNMEASockets(): Promise<void> {
      this.updating_nmea_sockets_debounced = false

      await nmea_injector.fetchAvailableNMEASockets()

      setTimeout(() => {
        this.updating_nmea_sockets_debounced = true
      }, 300)
    },
    openCreationDialog(): void {
      this.show_creation_dialog = true
    },
    createLink(sentence: string): string {
      const id = sentence.toLowerCase().substring(2)
      return `<a href="http://aprs.gids.nl/nmea/#${id}" target="_blank" rel="noopener noreferrer">${sentence}</a>`
    },
  },
})
</script>

<style scoped>
.injectors-list {
  background-color: transparent;
  max-width: 70%;
  margin: auto;
}
</style>
