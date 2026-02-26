<template>
  <v-card class="mt-4 mb-4">
    <v-card-text>
      <v-row align="center">
        <v-col cols="6">
          <span class="text-h6">Relay {{ relay_number }} Control:</span>
        </v-col>
        <v-col cols="6" class="d-flex justify-end">
          <v-btn
            v-tooltip="'Turn relay off'"
            small
            @click="setRelay(0)"
          >
            <v-icon small left>
              mdi-power-off
            </v-icon>
            Relay Off
          </v-btn>
          <v-btn
            v-tooltip="'Turn relay on'"
            small
            @click="setRelay(1)"
          >
            <v-icon small left>
              mdi-power
            </v-icon>
            Relay On
          </v-btn>
        </v-col>
      </v-row>

      <v-row align="center">
        <v-col cols="6" class="pa0">
          <parameter-switch
            v-if="inverted_parameter"
            :parameter="inverted_parameter"
            :off-value="0"
            :on-value="1"
            label="Invert Output"
          />
        </v-col>
        <v-col cols="6" class="pa0">
          <parameter-switch
            v-if="default_parameter"
            :parameter="default_parameter"
            :off-value="0"
            :on-value="1"
            label="Startup State"
          />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavCmd } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'RelaySetup',
  props: {
    relayParameter: {
      type: Object as () => Parameter,
      required: true,
    },
  },
  computed: {
    relay_number(): number {
      return parseInt(this.relayParameter.name.match(/RELAY(\d+)_FUNCTION/)?.[1] ?? '0', 10)
    },
    inverted_parameter(): Parameter | undefined {
      return autopilot_data.parameter(`RELAY${this.relay_number}_INVERTED`)
    },
    default_parameter(): Parameter | undefined {
      return autopilot_data.parameter(`RELAY${this.relay_number}_DEFAULT`)
    },
  },
  methods: {
    setRelay(setting: number): void {
      // MAV_CMD_DO_SET_RELAY: param1 = relay instance (0-indexed), param2 = setting (0=off, 1=on, 2=toggle)
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_DO_SET_RELAY,
        this.relay_number - 1, // Convert to 0-indexed relay instance
        setting,
      )
    },
  },
})
</script>
