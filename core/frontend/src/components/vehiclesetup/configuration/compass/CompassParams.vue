<template>
  <div>
    <v-simple-table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(parameter, index2) in compass_params " :key="index2" @click="openParameterEditor(parameter)">
          <td>{{ parameter.name }}</td>
          <td>{{ printParam(parameter) }}</td>
        </tr>
      </tbody>
    </v-simple-table>
    <parameter-editor-dialog
      v-model="edit_param_dialog"
      :param="edited_param"
    />
    <reboot-required-overlay />
  </div>
</template>

<script lang="ts">
import RebootRequiredOverlay from '@/components/common/rebootRequiredOverlay.vue'
import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'

export default {
  name: 'CompassParams',
  components: {
    RebootRequiredOverlay,
  },
  props: {
    index: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      edit_param_dialog: false,
      edited_param: undefined as Parameter | undefined,
    }
  },
  computed: {
    str_index() {
      return this.index === 1 ? '' : this.index
    },
    compass_params(): Parameter[] {
      // Espcial case for EXTERN, which changes from EXTERNAL to EXTERN1, EXTERN2, etc.
      let extern = []
      if (this.str_index === '') {
        extern = autopilot_data.parameterRegex('^COMPASS_EXTERNAL')
      } else {
        extern = autopilot_data.parameterRegex(`^COMPASS_EXTERN${this.str_index}`)
      }

      const params = [
        ...autopilot_data.parameterRegex(`^COMPASS_DIA${this.str_index}_.*`),
        ...autopilot_data.parameterRegex(`^COMPASS_OFS${this.str_index}_.*`),
        ...autopilot_data.parameterRegex(`^COMPASS_ODI${this.str_index}_.*`),
        ...autopilot_data.parameterRegex(`^COMPASS_ORIENT${this.str_index}_.*`),
        ...autopilot_data.parameterRegex(`^COMPASS_USE${this.str_index}_.*`),
        ...autopilot_data.parameterRegex(`^COMPASS_MOT${this.str_index}_.*`),
        ...autopilot_data.parameterRegex(`^COMPASS_SCALE${this.str_index}$`),
        ...autopilot_data.parameterRegex(`^COMPASS_DEV_ID${this.str_index}$`),
        ...extern,
      ]
      return params
    },
  },
  methods: {
    openParameterEditor(parameter: Parameter | undefined) {
      if (parameter) {
        this.edited_param = parameter
        this.edit_param_dialog = true
      }
    },
    printParam,
  },
}
</script>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  border: 1px solid #ddd;
  padding: 8px;
  cursor: pointer;
}

</style>
