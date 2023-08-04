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
            <span><b>Current:</b> {{ raspberry_eeprom_data.current_bootloader }} </span>
            <span v-if="bootloader_update_available">
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
            <span v-if="vl085_update_available">
              <b>Latest:</b> {{ raspberry_eeprom_data.latest_vl085 }}
            </span>
            <span v-else>
              <b>Up to date</b>
            </span>
          </div>
        </div>
      </v-card-text>

      <div
        class="d-flex flex-column align-center"
      >
        <v-btn
          v-if="update_available"
          elevated
          color="primary"
          class="ml-3"
          :loading="waiting_for_update"
          @click="doRaspiEEPROMUpdate"
        >
          Update
        </v-btn>
        <v-alert
          v-if="raspberry_eeprom_reboot_pending"
          type="success"
        >
          Changes applied, please do a <b>system reboot</b>.
        </v-alert>
      </div>
    </v-card>
  </v-sheet>
</template>

<script lang="ts">
import { formatRFC7231 } from 'date-fns'
import Vue from 'vue'

import commander from '@/store/commander'
import { ReturnStruct } from '@/types/commander'

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
      do_eeprom_update: undefined as undefined | ReturnStruct,
      vcgencmd: undefined as undefined | Record<string, ReturnStruct>,
      waiting_for_update: false,
    }
  },
  computed: {
    bootloader_update_available(): boolean {
      if (this.raspberry_eeprom_data.current_bootloader === undefined
        || this.raspberry_eeprom_data.latest_bootloader === undefined) {
        return false
      }
      return new Date(this.raspberry_eeprom_data.current_bootloader)
        < new Date(this.raspberry_eeprom_data.latest_bootloader)
    },
    vl085_update_available(): boolean {
      return this.raspberry_eeprom_data.current_vl085 !== this.raspberry_eeprom_data.latest_vl085
    },
    update_available(): boolean {
      if (this.raspberry_eeprom_reboot_pending) {
        return false
      }
      return this.bootloader_update_available || this.vl085_update_available
    },
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
      const data = this.raspiberry_firmware
        ?.split('\n')
        ?.[0]
      return this.formatDate(data)
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
        latest_bootloader: this.formatDate(latest?.[0]),
        current_bootloader: this.formatDate(current?.[0]),
        latest_vl085: latest?.[1],
        current_vl085: current?.[1],
      }
    },
    raspberry_eeprom_reboot_pending(): boolean {
      const lines = this.cleanUpString(this.do_eeprom_update?.stdout)?.split('\n') ?? []
      return lines.some((line) => line.includes('reboot to apply'))
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
    async doRaspiEEPROMUpdate() {
      this.waiting_for_update = true
      this.do_eeprom_update = await commander.doRaspiEEPROMUpdate()
      this.waiting_for_update = false
    },
    formatDate(date_value: string | undefined): string | undefined {
      if (date_value === undefined) {
        return undefined
      }

      return formatRFC7231(Date.parse(date_value)) ?? date_value
    },
    formatError(output: ReturnStruct | undefined): string | undefined {
      const return_code = output?.return_code
      if (return_code === undefined || return_code === 0) {
        return undefined
      }
      return this.cleanUpString(output?.stdout)
    },
    async getData(): Promise<void> {
      await Promise.all([
        commander.getVcgencmd().then((vcgencmd) => { this.vcgencmd = vcgencmd }),
        commander.getRaspiEEPROM().then((eeprom_update) => { this.eeprom_update = eeprom_update }),
      ])
    },
  },
})
</script>

<style>
  .card_style {
    width: 600px;
  }
</style>
