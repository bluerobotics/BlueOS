<template>
  <v-expansion-panel
    flat
  >
    <v-expansion-panel-header>
      {{ adapter.name }}
      <v-spacer />
      {{ status_info }}
    </v-expansion-panel-header>

    <v-expansion-panel-content>
      <v-row align="center">
        <v-col cols="10">
          <v-form
            ref="form"
            lazy-validation
          >
            <v-simple-table dense>
              <template #default>
                <tbody>
                  <tr>
                    <td>Name</td>
                    <td>{{ adapter.name }}</td>
                  </tr>

                  <tr>
                    <td>Mode</td>
                    <td v-if="!editing">
                      {{ showable_mode_name(adapter.configuration.mode) }}
                    </td>

                    <td v-else>
                      <v-select
                        v-model="mode_set"
                        dense
                        :items="mode_types"
                        required
                      />
                    </td>
                  </tr>

                  <tr>
                    <td>IP address</td>
                    <td v-if="!editing">
                      {{ current_ip }}
                    </td>

                    <td
                      v-else
                    >
                      <div v-if="editable_ip">
                        <v-text-field
                          v-model="ip_set"
                          label="IP Address"
                          single-line
                          dense
                          class="pa-1"
                        />
                      </div>
                    </td>
                  </tr>
                </tbody>
              </template>
            </v-simple-table>
          </v-form>
        </v-col>

        <v-col cols="2">
          <v-btn
            v-if="!editing"
            icon
            @click="changeEditing(true)"
          >
            <v-icon>mdi-pencil</v-icon>
          </v-btn>

          <v-container v-else>
            <v-row>
              <v-btn
                icon
                @click="emitEdit()"
              >
                <v-icon>mdi-check</v-icon>
              </v-btn>
            </v-row>

            <v-row>
              <v-btn
                icon
                @click="changeEditing(false)"
              >
                <v-icon>mdi-close</v-icon>
              </v-btn>
            </v-row>
          </v-container>
        </v-col>
      </v-row>
    </v-expansion-panel-content>
  </v-expansion-panel>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { EthernetInterface, InterfaceConfiguration, InterfaceMode } from '@/types/ethernet'

export default Vue.extend({
  name: 'NetworkCard',
  props: {
    adapter: {
      type: Object as PropType<EthernetInterface>,
      required: true,
    },
  },
  data() {
    return {
      editing: false,
      mode_set: this.adapter.configuration.mode,
      ip_set: this.adapter.configuration.ip,
    }
  },
  computed: {
    mode_types(): {value: InterfaceMode, text: string}[] {
      return Object.entries(InterfaceMode).map(
        (mode) => ({ value: mode[1], text: this.showable_mode_name(mode[1]) }),
      )
    },
    is_connected(): boolean {
      return this.adapter.info ? this.adapter.info.connected : false
    },
    current_ip(): string {
      return this.adapter.configuration.ip === 'undefined' ? 'Undefined IP' : this.adapter.configuration.ip
    },
    editable_ip(): boolean {
      return this.mode_set === InterfaceMode.unmanaged
    },
    status_info(): string {
      if (!this.is_connected) {
        return 'Not connected'
      }

      if (this.adapter.configuration.mode === InterfaceMode.server) {
        return 'DHCP Server running'
      }
      return this.adapter.configuration.ip
    },
  },
  methods: {
    showable_mode_name(mode: InterfaceMode): string {
      switch (mode) {
        case InterfaceMode.client: return 'Dynamic IP'
        case InterfaceMode.server: return 'DHCP Server'
        case InterfaceMode.unmanaged: return 'Static IP'
        default: return 'Undefined mode'
      }
    },
    changeEditing(state: boolean): void {
      this.editing = state
    },
    emitEdit() {
      const interface_configuration: InterfaceConfiguration = {
        mode: this.mode_set,
        ip: this.ip_set,
      }
      const changed_interface: EthernetInterface = {
        name: this.adapter.name,
        configuration: interface_configuration,
      }
      this.$emit('edit', changed_interface)

      this.changeEditing(false)
      this.ip_set = ''
    },
  },
})
</script>

<style>
.adapter-mode
{
  cursor: pointer;
}
</style>
