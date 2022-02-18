<template>
  <v-card
    width="500"
    elevation="0"
    class="mx-auto my-6"
  >
    <v-data-table
      :headers="[{ text: 'Name', value: 'name' },
                 { text: 'Value', value: 'value' }]"
      :items="params"
      item-key="name"
      class="elevation-1"
      :search="search"
      :custom-filter="filterOnlyCapsText"
    >
      <template #top>
        <v-text-field
          v-model="search"
          label="Search (UPPER CASE ONLY)"
          class="mx-4"
        />
      </template>
    </v-data-table>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

// import SpinningLogo from '../common/SpinningLogo.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import Listener from '@/libs/MAVLink2Rest/Listener'

import Parameter from './Parameter'
import ParametersTable from './ParameterTable'

export default Vue.extend({
  name: 'ParameterEditor',
  components: {
    // SpinningLogo,
  },
  data() {
    return {
      search: '',
      param_table: new ParametersTable(),
      params: [] as Parameter[],
      listener: null as (null | Listener),
    }
  },
  mounted() {
    this.setupWs()
    this.requestParams()
  },
  beforeDestroy() {
    this.listener?.discard()
  },
  methods: {
    requestParams() {
      mavlink2rest.sendMessage(
        {
          header: {
            system_id: 255,
            component_id: 0,
            sequence: 0,
          },
          message: {
            type: 'PARAM_REQUEST_LIST',
            target_system: 0,
            target_component: 0,
          },
        },
      )
    },
    setupWs() {
      this.listener = mavlink2rest.startListening('PARAM_VALUE').setCallback((receivedMessage) => {
        if (receivedMessage.count > 0) {
          this.param_table.setCount(receivedMessage.count)
        }
        this.param_table.addParam(new Parameter(receivedMessage.param_id.join(''), receivedMessage.param_value))
        this.params = this.param_table.parameters // force update with reactivity
      }).setFrequency(0)
    },
    filterOnlyCapsText(value: string, search: string, item: any) {
      return value != null
        && search != null
        && typeof value === 'string'
        && value.toString().toLocaleUpperCase().indexOf(search) !== -1
    },
  },
})
</script>
