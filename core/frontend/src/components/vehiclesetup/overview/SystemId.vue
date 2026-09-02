<template>
  <v-card class="pa-1" elevation="2">
    <v-card-title class="d-flex align-center">
      Configure MAVLink system ID
    </v-card-title>
    <v-card-text>
      Note that it is necessary to restart the BlueOS core container in order for the vehicle ID change to fully
      take place.
    </v-card-text>
    <v-card-text>
      <inline-parameter-editor
        v-if="mav_sysid"
        :param="mav_sysid"
        :label="'MAVLink system ID'"
        @change="pending_value = $event"
        @form-valid-change="is_form_valid = $event"
      />
      <v-alert
        v-if="save_error"
        type="error"
        dense
        text
        class="mt-3 mb-0"
      >
        Failed to set system ID: {{ save_error }}
      </v-alert>
    </v-card-text>
    <v-card-actions class="justify-end">
      <v-btn
        v-tooltip="'Restart the BlueOS core container'"
        :loading="restarting_core"
        :disabled="restarting_core || saving"
        @click="restartCore"
      >
        <v-icon left color="orange">
          mdi-folder-refresh
        </v-icon>
        Restart Core
      </v-btn>
      <v-btn
        color="primary"
        :loading="saving"
        :disabled="!can_save || saving"
        @click="save"
      >
        Save
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import InlineParameterEditor from '@/components/parameter-editor/InlineParameterEditor.vue'
import Notifier from '@/libs/notifier'
import autopilot from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(autopilot_service)

export default Vue.extend({
  name: 'SystemId',
  components: {
    InlineParameterEditor,
  },
  data() {
    return {
      pending_value: undefined as number | undefined,
      is_form_valid: true,
      restarting_core: false,
      saving: false,
      save_error: undefined as string | undefined,
    }
  },
  computed: {
    mav_sysid(): Parameter | undefined {
      return autopilot.parameter('MAV_SYSID')
    },
    has_pending_change(): boolean {
      return this.mav_sysid !== undefined
        && this.pending_value !== undefined
        && this.pending_value !== this.mav_sysid.value
    },
    can_save(): boolean {
      return this.has_pending_change && this.is_form_valid
    },
  },
  methods: {
    async save(): Promise<void> {
      if (!this.mav_sysid || this.pending_value === undefined) {
        return
      }

      this.save_error = undefined
      this.saving = true
      await back_axios({
        method: 'post',
        url: `/autopilot-manager/v1.0/system_id?value=${this.pending_value}`,
      }).catch((error) => {
        this.save_error = error.response?.data?.detail ?? error.response?.data ?? error.message
        notifier.pushBackError('SET_MAV_SYSTEM_ID', error)
      }).finally(() => {
        this.saving = false
      })
    },
    async restartCore(): Promise<void> {
      this.restarting_core = true
      await back_axios({
        method: 'post',
        url: '/version-chooser/v1.0/version/restart',
      }).finally(() => {
        // Give the backend a bit to go down, then reload so the user reconnects to the fresh core
        setTimeout(() => window.location.reload(), 15000)
      })
    },
  },
})
</script>
