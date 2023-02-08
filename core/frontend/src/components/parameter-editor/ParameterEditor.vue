<template>
  <v-card
    elevation="0"
    class="mx-auto my-6"
  >
    <v-data-table
      :headers="[
        { text: 'Name', value: 'name' },
        { text: 'Description', value: 'description' },
        { text: 'Value', value: 'value', width: '150px' },
      ]"
      :loading="!finished_loading"
      :items="search != '' ? fuse.search(search) : params_no_input"
      item-key="item.name"
      class="elevation-1"
      :search="search"
      :sort-by="'name'"
      disable-sort
      :custom-filter="() => true"
      @click:row="(value) => editParam(value.item)"
    >
      <v-progress-linear
        slot="progress"
        color="blue"
        height="20"
        :value="params_percentage"
      >
        <template #default>
          <strong
            v-if="!finished_loading && params_percentage > 99.9"
          >
            Waiting for metadata.. </strong>
          <strong
            v-if="params_percentage == 0"
            class="ml-5"
          > Waiting for parameters.. </strong>
          <strong
            v-if="params_percentage > 0 && params_percentage < 100"
            class="ml-5"
          >
            {{ params_percentage.toFixed(1) }}% ({{ loaded_parameters }} / {{ total_parameters }})
          </strong>
        </template>
      </v-progress-linear>
      <template #top>
        <v-text-field
          v-model="search"
          label="Search"
          class="mx-4"
          clearable
          prepend-inner-icon="mdi-magnify"
        />
      </template>
      <!-- suprresing no-vue-html -->
      <!-- eslint-disable -->
      <template #item.name="{ item }">
        <div v-html="printMark(item, 'name')" />
      </template>
      <template #item.description="{ item }">
        <div v-html="printMark(item, 'description')" />
      </template>
       <!-- eslint-enable -->
      <template #item.value="{ item }">
        {{ printParam(item.item) }} {{ item.item.units ? `[${item.item.units}]` : '' }}
      </template>
      <template #footer.prepend>
        <v-btn
          v-tooltip="'Save all parameters to file'"
          :disabled="!finished_loading"
          color="primary"
          class="mr-5"
          @click="saveParametersToFile()"
        >
          <v-icon class="mr-2">
            mdi-tray-arrow-down
          </v-icon>
          <div>Save</div>
        </v-btn>
        <v-btn
          v-tooltip="'Load parameters from file'"
          :disabled="!finished_loading"
          class="mr-5"
          color="primary"
          @click="load_param_dialog = true"
        >
          <v-icon class="mr-2">
            mdi-tray-arrow-up
          </v-icon>
          <div>Load</div>
        </v-btn>
        <v-btn
          v-if="need_vehicle_reboot"
          v-tooltip="'A parameter that requires a vehicle reboot was changed'"
          :disabled="!finished_loading"
          color="warning"
          class="mr-5"
          @click="rebootVehicle()"
        >
          <div>Reboot vehicle</div>
        </v-btn>
      </template>
    </v-data-table>
    <v-dialog
      v-model="edit_dialog"
      max-width="500px"
    >
      <v-card>
        <v-card-title>
          <span class="text-h5">{{ edited_param?.name ?? '' }}</span>
        </v-card-title>

        <v-card-text>
          <v-container
            v-if="edited_param"
          >
            <v-row v-if="edited_param.rebootRequired">
              Reboot Required
            </v-row>
            <v-row>
              {{ edited_param.description }}
            </v-row>
            <v-row
              v-if="edited_param.range"
              class="pt-6"
            >
              Min: {{ edited_param.range.low }}
              Max: {{ edited_param.range.high }}
              Increment: {{ edited_param.increment ?? 0.01 }}
            </v-row>
            <v-row>
              <v-col
                cols="6"
                sm="6"
                md="6"
              >
                <v-form
                  ref="form"
                >
                  <template v-if="!custom_input && edited_param.bitmask">
                    <v-checkbox
                      v-for="(key, value) in edited_param?.bitmask"
                      :key="value"
                      v-model="edited_bitmask"
                      dense
                      :label="key"
                      :value="2 ** value"
                    />
                  </template>
                  <v-select
                    v-else-if="!custom_input && edited_param?.options"
                    v-model.number="new_value"
                    :items="as_select_tems"
                    :rules="[() => true]"
                  />
                  <v-text-field
                    v-if="custom_input || (edited_param && !edited_param.options && !edited_param.bitmask)"
                    v-model.number="new_value"
                    label="Value"
                    type="number"
                    :step="edited_param.increment ?? 0.01"
                    :suffix="edited_param.units"
                    :rules="forcing_input ? [] : [isInRange, isValidType]"
                  />

                  <v-checkbox
                    v-if="show_advanced_checkbox"
                    v-model="forcing_input"
                    dense
                    :label="'Force'"
                  />
                  <v-checkbox
                    v-if="show_custom_checkbox"
                    v-model="custom_input"
                    dense
                    :label="'Custom'"
                  />
                </v-form>
              </v-col>
            </v-row>
          </v-container>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            color="primary"
            @click="edit_dialog = false"
          >
            Cancel
          </v-btn>
          <v-btn
            :disabled="paramValueNotChanged"
            color="primary"
            @click="saveEditedParam()"
          >
            Save
          </v-btn>
          <v-btn
            v-if="edited_param?.rebootRequired === true"
            v-tooltip="'Reboot required for parameter to take effect'"
            :disabled="paramValueNotChanged"
            color="warning"
            @click="saveEditedParam(true)"
          >
            Save and Reboot
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog
      v-model="load_param_dialog"
      max-width="500px"
    >
      <v-card>
        <v-card-title>
          <span class="text-h5">Load parameter file</span>
        </v-card-title>

        <v-card-text>
          <v-container>
            <v-row>
              <v-file-input
                accept=".txt"
                class="mr-2"
                show-size
                label="Parameter file"
                @change="setParameterFile"
              />
            </v-row>
            <!--v-row>
              <v-col cols="6" sm="6" md="6">
                <v-form ref="form">
                  <v-checkbox v-if="show_advanced_checkbox" v-model="forcing_input" dense :label="'Force'" />
                  <v-checkbox v-if="show_custom_checkbox" v-model="custom_input" dense :label="'Custom'" />
                </v-form>
              </v-col>
            </v-row-->
          </v-container>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            color="primary"
            @click="load_param_dialog = false"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            @click="applyParameterFile"
          >
            Save and Reboot
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script lang="ts">
import { format } from 'date-fns'
import { saveAs } from 'file-saver'
import Fuse from 'fuse.js'
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import Notifier from '@/libs/notifier'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import Parameter, { ParamType, printParam } from '@/types/autopilot/parameter'
import { parameters_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import back_axios from '@/utils/api'

const notifier = new Notifier(parameters_service)

export default Vue.extend({
  name: 'ParameterEditor',
  data() {
    return {
      search: '',
      edited_param: undefined as (undefined | Parameter),
      edit_dialog: false,
      edited_bitmask: [] as number[],
      forcing_input: false,
      load_param_dialog: false,
      loaded_parameter: [] as {name: string, value: number, type: undefined | ParamType}[],
      custom_input: false,
      new_value: 0,
      need_vehicle_reboot: false,
    }
  },
  computed: {
    fuse() {
      return new Fuse(autopilot_data.parameters, {
        keys: ['name', 'description'],
        includeScore: true,
        includeMatches: true,
        shouldSort: true,
        threshold: 0.3,
        minMatchCharLength: 2,
      })
    },
    params_no_input() {
      return autopilot_data.parameters
        .sort((a, b) => {
          if (a.name > b.name) {
            return 1
          }
          if (b.name > a.name) {
            return -1
          }
          return 0
        })
        .map((param) => ({
          item: param,
        }))
    },
    params_percentage() {
      return 100 * (autopilot_data.parameters.length / autopilot_data.parameters_total)
    },
    loaded_parameters() {
      return autopilot_data.parameters.length
    },
    total_parameters() {
      return autopilot_data.parameters_total
    },
    finished_loading() {
      return autopilot_data.finished_loading
    },
    form(): VForm {
      return this.$refs.form as VForm
    },
    show_advanced_checkbox(): boolean {
      return typeof this.isInRange(this.new_value ?? 0) === 'string'
    },
    show_custom_checkbox(): boolean {
      return !!(this.edited_param?.options || this.edited_param?.bitmask)
    },
    as_select_tems() {
      const entries = Object.entries(this.edited_param?.options ?? [])
      return entries.map(([value, name]) => ({ text: name, value: parseFloat(value), disabled: false }))
    },
    editedBitmaskValue(): number {
      return this.edited_bitmask.reduce((accumulator, current) => accumulator + current, 0)
    },
    paramValueNotChanged(): boolean {
      // Check if value is different
      return this.new_value === this.edited_param?.value
        // Check if bitmask value, if valid, is different from current value
        && (this.edited_param?.bitmask === undefined || this.editedBitmaskValue === this.edited_param?.value)
    },
  },
  watch: {
    edit_dialog(): void {
      if (!this.edit_dialog) {
        this.forcing_input = false
        this.custom_input = false
      }

      // Select force input if value is outside of range initially
      this.forcing_input = typeof this.isInRange(this.new_value) === 'string'

      // Select custom input if value is outside of possible options
      this.custom_input = !Object.keys(this.edited_param?.options ?? [])
        .map((value) => parseFloat(value))
        .includes(this.new_value)
    },
    new_value(): void {
      // Remove forcing_input once option is inside valid range
      if (this.forcing_input && typeof this.isInRange(this.new_value) === 'boolean') {
        this.forcing_input = false
      }

      // Remove custom once value is known
      if (this.custom_input) {
        this.custom_input = !Object.keys(this.edited_param?.options ?? [])
          .map((value) => parseFloat(value))
          .includes(this.new_value)
      }
    },
  },
  methods: {
    isInRange(input: number | string): boolean | string {
      // The input value is an empty string when the field is empty
      if (typeof input === 'string' && input?.trim().length === 0) {
        return 'This should be a number between min and max'
      }

      if (!this.edited_param?.range) {
        return true
      }
      if (input > this.edited_param.range.high) {
        return `Value should be smaller than ${this.edited_param.range.high}`
      }
      if (input < this.edited_param.range.low) {
        return `Value should be greater than ${this.edited_param.range.low}`
      }
      return true
    },
    isValidType(input: number): boolean | string {
      if (this.edited_param?.paramType.type.includes('UINT')) {
        if (input < 0) {
          return 'This parameter must be a positive Integer'
        }
      }
      if (this.edited_param?.paramType.type.includes('INT')) {
        if (!Number.isInteger(input)) {
          return 'This parameter must be an Integer'
        }
      }
      return true
    },
    editParam(param: Parameter) {
      if (param.readonly) {
        return
      }
      this.edited_param = param
      this.new_value = this.edited_param?.value ?? 0
      this.edit_dialog = true
      this.edited_bitmask = []
      if (param.bitmask === undefined) {
        return
      }
      // eslint-disable-next-line no-bitwise
      for (let v = 0; 1 << v < param.value; v += 1) {
        // eslint-disable-next-line no-bitwise
        const bitmask_value = 1 << v
        // eslint-disable-next-line no-bitwise
        if (bitmask_value & param.value) {
          this.edited_bitmask.push(bitmask_value)
        }
      }
    },
    async saveEditedParam(reboot = false) {
      if (!this.forcing_input && !this.form?.validate()) {
        return
      }
      this.edit_dialog = false
      if (this.edited_param == null) {
        return
      }
      if (!this.custom_input && this.edited_param.bitmask !== undefined) {
        this.new_value = this.editedBitmaskValue
      }
      let value = 0
      if (typeof this.new_value === 'string') {
        value = parseFloat(this.new_value)
      } else {
        value = this.new_value
      }

      mavlink2rest.setParam(this.edited_param.name, value, this.edited_param.paramType.type)

      if (reboot) {
        await this.rebootVehicle()
      } else if (this.edited_param.rebootRequired) {
        this.need_vehicle_reboot = true
      }
    },
    async rebootVehicle(): Promise<void> {
      await this.restart_autopilot()
      autopilot_data.reset()
    },
    async restart_autopilot(): Promise<void> {
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/restart`,
        timeout: 10000,
      })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_RESTART_FAIL', error)
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
    printMark(item: Fuse.FuseResult<Record<string, string>>, key: string): string {
      const name = item.item[key]
      const indices_array = item?.matches?.find((i: Fuse.FuseResultMatch) => i.key === key)?.indices ?? []

      let indices = indices_array?.[0]
      for (const index of indices_array) {
        if (indices[1] - indices[0] < index[1] - index[0]) {
          indices = index
        }
      }

      const matche = indices ? name.substring(indices[0], indices[1] + 1) : ''
      return indices ? name.replace(matche, `<mark>${matche}</mark>`) : name
    },
    printParam,
    saveParametersToFile() {
      let parameter_name_max_size = 0

      // Sort parameters alphabetically
      // We take advantage of sort to also calculate the parameter name maximum size
      const parameters = Object.values(autopilot_data.parameters).sort((first, second) => {
        parameter_name_max_size = Math.max(parameter_name_max_size, first.name.length)
        parameter_name_max_size = Math.max(parameter_name_max_size, second.name.length)

        if (first.name < second.name) {
          return -1
        }
        if (first.name > second.name) {
          return 1
        }
        return 0
      })

      let content = ''

      const vehicle = autopilot.vehicle_type ?? 'vehicle'
      const platform = autopilot.current_board?.platform ?? 'platform'
      const version = autopilot.firmware_info?.version ?? 'version'
      const type = autopilot.firmware_info?.type ?? 'None'
      const date = format(new Date(), 'yyyyMMdd-HHmmss')

      content += `# Date: ${new Date()}\n`
      content += `# Vehicle: ${vehicle}\n`
      content += `# Platform: ${platform}\n`
      content += `# Version: ${version}-${type}\n\n`
      content += '# Parameters\n'

      const file_name = `${vehicle}-${version}-${type}-${date}`

      for (const param of parameters) {
        // Calculate space between name and value to make it pretty
        const space = Array(parameter_name_max_size - param.name.length + 2).join(' ')
        content += `${param.name}${space}${param.value}\n`
      }

      const file = new File([content], `${file_name}.txt`, { type: 'text/plain' })
      saveAs(file)
    },
    async setParameterFile(file: (File | null)): Promise<void> {
      const content = await file?.text()
      const lines = content?.split(/\r?\n/)
      const new_parameters = lines
        ?.map((line) => line.trim())
        ?.filter((line) => line[0] !== '#' && line.length !== 0)
        ?.map((line) => {
          const [name, value] = line.split(/ {1,}/)
          const type = autopilot_data.parameters.find((param) => param.name === name)?.paramType.type
          return { name, value: parseFloat(value), type }
        })
      this.loaded_parameter = new_parameters ?? []
    },
    applyParameterFile(): void {
      for (const param of this.loaded_parameter) {
        mavlink2rest.setParam(param.name, param.value, param.type)
      }
      this.load_param_dialog = false
    },
  },
})
</script>

<style>
div.v-messages {
  min-height: 1px;
}
</style>
