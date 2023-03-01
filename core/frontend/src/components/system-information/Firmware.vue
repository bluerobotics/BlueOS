<template>
  <v-sheet
    shaped
    class="pa-6 d-flex flex-column align-center"
    style="min-width: 600px;"
  >
    <v-card
      class="ma-2 pa-2 card_style"
      :loading="vcgencmd === undefined"
    >
      <v-card-title class="align-center">
        Raspberry Firmware
      </v-card-title>
      <v-card-text>
        <div v-if="raspberry_firmware_error">
          <span><b> {{ raspberry_firmware_error }} </b> </span>
        </div>
        <div v-else>
          <span class="d-block"><b>From:</b> {{ raspiberry_firmware_data }} </span>
          <span class="d-block"><b>Version:</b> {{ raspberry_firmware_version }} </span>
        </div>
      </v-card-text>
    </v-card>

    <v-card
      class="ma-2 pa-2 card_style"
      :loading="vcgencmd === undefined"
    >
      <v-card-title class="align-center">
        Bootloader Version
      </v-card-title>
      <v-card-text>
        <div v-if="raspberry_bootloader_error">
          <span><b> {{ raspberry_bootloader_error }} </b> </span>
        </div>
        <div v-else>
          <span class="d-block"><b>From:</b> {{ raspiberry_bootloader_data }} </span>
          <span class="d-block"><b>Version:</b> {{ raspberry_bootloader_version }} </span>
        </div>
      </v-card-text>
    </v-card>

    <v-card
      class="ma-2 pa-2 card_style"
      :loading="vcgencmd === undefined"
    >
      <v-card-title class="align-center">
        VL085 Version (USB Controller)
      </v-card-title>
      <v-card-text>
        <div v-if="raspberry_vl085_error">
          <span><b> {{ raspberry_vl085_error }} </b> </span>
        </div>
        <div v-else>
          <span class="d-block"><b>Version:</b> {{ raspberry_vl085_version }} </span>
        </div>
      </v-card-text>
    </v-card>
  </v-sheet>
</template>

<script lang="ts">
import Vue from 'vue'

import back_axios from '@/utils/api'

interface ReturnStruct {
  stdout: string
  stderr: string
  return_code: number
}

export default Vue.extend({
  name: 'Processes',
  data() {
    return {
      vcgencmd: undefined as undefined | Record<string, ReturnStruct>,
    }
  },
  computed: {
    raspiberry_firmware(): string | undefined {
      return this.cleanUpString(this.vcgencmd?.firmware?.stdout)
    },
    raspiberry_firmware_data(): string | undefined {
      return this.raspiberry_firmware
        ?.split('\n')
        ?.[0]
    },
    raspberry_firmware_version(): string | undefined {
      return this.raspiberry_firmware
        ?.split('\n')
        ?.[2]
        ?.split('version ')
        ?.[1]
    },
    raspberry_firmware_error(): string | undefined {
      return this.formatError(this.vcgencmd?.firmware)
    },
    raspiberry_bootloader(): string | undefined {
      return this.cleanUpString(this.vcgencmd?.bootloader?.stdout)
    },
    raspiberry_bootloader_data(): string | undefined {
      return this.raspiberry_bootloader
        ?.split('\n')
        ?.[0]
    },
    raspberry_bootloader_version(): string | undefined {
      return this.raspiberry_bootloader
        ?.split('\n')
        ?.[1]
        ?.split('version ')
        ?.[1]
    },
    raspberry_bootloader_error(): string | undefined {
      return this.formatError(this.vcgencmd?.bootloader)
    },
    raspberry_vl085_version(): string | undefined {
      return this.cleanUpString(this.vcgencmd?.vl085?.stdout)
        ?.split('\n')
        ?.find((x) => x.includes('28:'))
        ?.substring(3)
    },
    raspberry_vl085_error(): string | undefined {
      return this.formatError(this.vcgencmd?.vl085)
    },
  },
  async mounted() {
    await this.getVcgencmd()
  },
  methods: {
    cleanUpString(text: string | undefined): string | undefined {
      if (text === undefined) {
        return text
      }
      return text.slice(1, -1).replace(/\\n/g, '\n').trim().trim()
    },
    formatError(output: ReturnStruct | undefined): string | undefined {
      const return_code = output?.return_code
      if (return_code === undefined || return_code === 0) {
        return undefined
      }
      return this.cleanUpString(output?.stdout)
    },
    async getVcgencmd(): Promise<void> {
      await back_axios({
        url: '/commander/v1.0/raspi/vcgencmd?',
        method: 'get',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 10000,
      })
        .then((response) => {
          this.vcgencmd = response.data
        })
        .catch((error) => {
          // Connection lost/timeout, normal when we are turning off/rebooting
          if (error.code === 'ECONNABORTED') {
            return
          }

          console.warn('Failed to fetch vcgencmd info:')
          console.warn(error)
        })
    },
  },
})
</script>

<style>
  .card_style {
    width: 600px;
  }
</style>
