<template>
  <v-card v-if="status === 'VALID'" class="card-container">
    <v-card-title class="align-center">
      Calibration Backup
    </v-card-title>
    <v-card-text>
      <p>
        Save your calibrations on the Navigator EEPROM so they stay with the board,
        and load them back whenever you need.
      </p>
    </v-card-text>
    <v-card-actions class="flex-wrap justify-center justify-sm-start">
      <v-tooltip bottom :disabled="disabled_reason === null">
        <template #activator="{ on }">
          <span v-on="on">
            <v-btn
              color="primary"
              :disabled="disabled_reason !== null"
              :loading="saving"
              @click="save"
            >
              Save to EEPROM
            </v-btn>
            <v-btn
              color="primary"
              :disabled="disabled_reason !== null"
              @click="load"
            >
              Load from EEPROM
            </v-btn>
          </span>
        </template>
        <span>{{ disabled_reason }}</span>
      </v-tooltip>
    </v-card-actions>
    <WarningDialog
      v-model="show_warning"
      message="The EEPROM contains data that is not a calibration backup.
        Saving will permanently overwrite everything after the highlighted area. This action cannot be undone."
      confirm-label="Yes, overwrite"
      width="700"
      @confirm="backup"
    >
      <pre class="hexdump"><span class="info--text">{{ protected_text }}</span>{{ dump_text }}</pre>
    </WarningDialog>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import WarningDialog from '@/components/common/WarningDialog.vue'
import Notifier from '@/libs/notifier'
import { frontend_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(frontend_service)

const API_URL = '/ardupilot-manager/v1.0/eeprom'

const BLANK_BYTE = 0xFF
const BYTES_PER_ROW = 16

function toHex(value: number, width: number): string {
  return value.toString(16).padStart(width, '0')
}

// Trailing blank bytes are left out, so a mostly empty chip does not show hundreds of useless rows
function hexdump(bytes: Uint8Array, base = 0): string {
  let end = bytes.length
  while (end > 0 && bytes[end - 1] === BLANK_BYTE) {
    end -= 1
  }
  const rows = []
  for (let offset = 0; offset < end; offset += BYTES_PER_ROW) {
    const row = bytes.slice(offset, offset + BYTES_PER_ROW)
    const hex = Array.from(row, (byte) => toHex(byte, 2)).join(' ')
    const ascii = String.fromCharCode(...row).replace(/[^\x20-\x7E]/g, '.')
    rows.push(`${toHex(base + offset, 4)}  ${hex.padEnd(BYTES_PER_ROW * 3 - 1)}  ${ascii}`)
  }
  return rows.join('\n')
}

export default Vue.extend({
  name: 'EepromBackup',
  components: {
    WarningDialog,
  },
  data: () => ({
    status: undefined as (undefined | string),
    mavlink: false,
    saving: false,
    show_warning: false,
    dump_text: '',
    protected_text: '',
  }),
  computed: {
    disabled_reason(): string | null {
      return this.mavlink ? null : 'MAVLink is not available. Check if the autopilot is running and connected.'
    },
  },
  mounted() {
    this.fetchStatus()
  },
  methods: {
    async fetchStatus() {
      await back_axios({ method: 'get', url: `${API_URL}/status` })
        .then((response) => {
          this.status = response.data.status
          this.mavlink = response.data.mavlink
        })
        .catch((error) => notifier.pushBackError('EEPROM_STATUS_FAIL', error))
    },
    async save() {
      const response = await back_axios({ method: 'get', url: `${API_URL}/dump` })
        .catch((error) => notifier.pushBackError('EEPROM_DUMP_FAIL', error, true))
      if (!response) {
        return
      }
      const { data, backup_offset, hat_size } = response.data
      const dump = Uint8Array.from(atob(data), (char) => char.charCodeAt(0))
      // The board ID area is never written, so only the data after it can be overwritten
      const writable = dump.slice(hat_size)

      if (backup_offset !== null || writable.every((byte) => byte === BLANK_BYTE)) {
        this.backup()
        return
      }
      this.protected_text = hat_size > 0 ? `${hexdump(dump.slice(0, hat_size))}\n` : ''
      this.dump_text = hexdump(writable, hat_size)
      this.show_warning = true
    },
    async backup() {
      this.saving = true
      await back_axios({ method: 'post', url: `${API_URL}/backup`, timeout: 20000 })
        .then(() => notifier.pushSuccess('EEPROM_SAVE_SUCCESS', 'Calibrations saved on the EEPROM', true))
        .catch((error) => notifier.pushBackError('EEPROM_SAVE_FAIL', error, true))
        .finally(() => { this.saving = false })
    },
    async load() {
      await back_axios({ method: 'get', url: `${API_URL}/backup` })
        .then((response) => this.$emit('load', response.data))
        .catch((error) => notifier.pushBackError('EEPROM_LOAD_FAIL', error, true))
    },
  },
})
</script>

<style scoped>
button {
  margin: 10px;
}

.hexdump {
  max-height: 300px;
  width: fit-content;
  overflow: auto;
  margin-top: 10px;
  font-size: 0.8rem;
}
</style>
