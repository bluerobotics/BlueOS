<template>
  <v-dialog
    max-width="500px"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        <span class="text-h5">{{ param?.name ?? "" }}</span>
      </v-card-title>

      <v-card-text>
        <v-container v-if="param">
          <v-row v-if="param.rebootRequired">
            Reboot Required
          </v-row>
          <v-row>
            {{ param.description }}
          </v-row>
          <v-row
            v-if="param.range"
            class="pt-6"
          >
            Min: {{ param.range.low }} Max:
            {{ param.range.high }} Increment:
            {{ param.increment ?? 0.01 }}
          </v-row>
          <v-row>
            <v-col
              cols="6"
              sm="6"
              md="6"
            >
              <inline-parameter-editor
                v-if="param"
                v-model="new_value"
                :allow-custom="true"
                :param="param"
                @form-valid-change="formValidUpdate"
              />
            </v-col>
          </v-row>
        </v-container>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn
          color="primary"
          @click="showDialog(false)"
        >
          Cancel
        </v-btn>
        <v-btn
          :disabled="param_value_not_changed || !is_form_valid"
          color="primary"
          @click="saveEditedParam()"
        >
          Save
        </v-btn>
        <v-btn
          v-if="param?.rebootRequired === true"
          v-tooltip="'Reboot required for parameter to take effect'"
          :disabled="param_value_not_changed || !is_form_valid"
          color="warning"
          @click="saveEditedParam(true)"
        >
          Save and Reboot
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script lang="ts">
import Vue, { PropType } from 'vue'

import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'ParameterEditorDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    param: {
      type: Object as PropType<Parameter> | undefined,
      default: undefined,
    },
  },
  data() {
    return {
      // Form can't be computed correctly, so we save it's state under data
      is_form_valid: false,
      new_value: 0,
    }
  },
  computed: {
    param_value_not_changed(): boolean {
      return this.new_value === this.param?.value
    },
  },
  methods: {
    formValidUpdate(is_valid: boolean) {
      this.is_form_valid = is_valid
    },
    async rebootVehicle(): Promise<void> {
      await this.restart_autopilot()
      autopilot_data.reset()
    },
    async restart_autopilot(): Promise<void> {
      await AutopilotManager.restart()
    },
    async saveEditedParam(reboot = false) {
      mavlink2rest.setParam(this.param.name, this.new_value, autopilot_data.system_id, this.param.paramType.type)

      if (reboot) {
        await this.rebootVehicle()
        autopilot_data.setRebootRequired(false)
      } else if (this.param.rebootRequired) {
        autopilot_data.setRebootRequired(true)
      }
      this.$emit('change', false)
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>
