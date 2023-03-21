<template>
  <v-sheet
    shaped
    class="pa-6 d-flex flex-column align-center"
    style="min-width: 600px;"
  >
    <v-card
      class="ma-2 pa-2 card_style"
      :loading="loading_vcgencmd"
    >
      <v-card-title class="align-center">
        Raspberry Firmware
      </v-card-title>
      <v-card-text>
        <div v-if="raspberry_firmware_error">
          <span><b> {{ raspberry_firmware_error }} </b> </span>
        </div>
        <div v-else-if="!loading_vcgencmd">
          <span class="d-block"><b>From:</b> {{ raspiberry_firmware_data }} </span>
          <span class="d-block"><b>Version:</b> {{ raspberry_firmware_version }} </span>
        </div>
      </v-card-text>
    </v-card>

    <v-card
      class="ma-2 pa-2 card_style"
      :loading="loading"
    >
      <v-card-title class="align-center">
        Bootloader Version
      </v-card-title>
      <v-card-text>
        <div v-if="eeprom_update">
          <div class="d-flex justify-space-between">
            <span><b>From:</b> {{ raspberry_eeprom_data.current_bootloader }} </span>
            <span v-if="raspberry_eeprom_data.current_bootloader !== raspberry_eeprom_data.latest_bootloader">
              <b>Latest:</b> {{ raspberry_eeprom_data.latest_bootloader }}
            </span>
            <span v-else>
              <b>Up to date</b>
            </span>
          </div>
          <span v-if="raspberry_bootloader_version" class="d-block">
            <b>Version:</b> {{ raspberry_bootloader_version }}
          </span>
        </div>
        <div v-if="eeprom_update">
          <div class="d-flex justify-space-between mb-3">
            <span><b>VL085 Firmware (USB Controller):</b> {{ raspberry_eeprom_data.current_vl085 }} </span>
            <span v-if="raspberry_eeprom_data.current_vl085 !== raspberry_eeprom_data.latest_vl085">
              <b>Latest:</b> {{ raspberry_eeprom_data.latest_vl085 }}
            </span>
            <span v-else>
              <b>Up to date</b>
            </span>
          </div>
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

interface EepromUpdateStruct {
  latest_bootloader: string | undefined
  current_bootloader: string | undefined
  latest_vl085: string | undefined
  current_vl085: string | undefined
}

export default Vue.extend({
  name: 'Processes',
  data() {
    return {
      eeprom_update: undefined as undefined | ReturnStruct,
      vcgencmd: undefined as undefined | Record<string, ReturnStruct>,
    }
  },
  computed: {
    loading_vcgencmd(): boolean {
      return this.vcgencmd === undefined
    },
    loading(): boolean {
      return this.eeprom_update === undefined || this.vcgencmd === undefined
    },
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
    raspberry_bootloader_version(): string | undefined {
      return this.raspiberry_bootloader
        ?.split('\n')
        ?.[1]
        ?.split('version ')
        ?.[1]
    },
    raspberry_eeprom_data(): EepromUpdateStruct {
      const lines = this.cleanUpString(this.eeprom_update?.stdout)?.split('\n') ?? []

      const current = []
      const latest = []

      for (const line of lines) {
        const result = line.splitOnce(':')
        if (result === undefined) {
          continue
        }

        let [key, value] = result
        key = key.trim()
        value = value.trim()

        switch (key) {
          case 'CURRENT':
            current.push(value)
            break
          case 'LATEST':
            latest.push(value)
            break
          default:
            continue
        }
      }

      return {
        latest_bootloader: latest?.[0],
        current_bootloader: current?.[0],
        latest_vl085: latest?.[1],
        current_vl085: current?.[1],
      }
    },
  },
  async mounted() {
    await this.getData()
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
    async getData(): Promise<void> {
      const vcgencmd = back_axios({
        url: '/commander/v1.0/raspi/vcgencmd',
        method: 'get',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 20000,
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

      const eeprom = back_axios({
        url: '/commander/v1.0/raspi/eeprom_update',
        method: 'get',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 20000,
      })
        .then((response) => {
          this.eeprom_update = response.data
        })
        .catch((error) => {
          // Connection lost/timeout, normal when we are turning off/rebooting
          if (error.code === 'ECONNABORTED') {
            return
          }

          console.warn('Failed to fetch eeprom info:')
          console.warn(error)
        })

      Promise.all([vcgencmd, eeprom])
    },
  },
})
</script>

<style>
  .card_style {
    width: 600px;
  }
</style>
