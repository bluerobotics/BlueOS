<template>
  <v-dialog
    width="750px"
    :value="show"
    scrollable
    @input="showDialog"
  >
    <v-card
      min-width="750px"
      height="fit-content"
    >
      <v-card-title> Video configuration </v-card-title>
      <v-layout
        row
        no-gutters
      >
        <v-col cols="7">
          <v-card-text>
            <v-container v-if="are_controllers_available">
              <v-slider
                v-for="control in slider_controls"
                :key="control.id"
                v-model="control.configuration.Slider.value"
                :min="control.configuration.Slider.min"
                :max="control.configuration.Slider.max"
                :step="control.configuration.Slider.step"
                :label="control.name"
                :disabled="!isActive(control)"
                @change="updateControlsValues([control])"
              />
              <v-select
                v-for="control in menu_controls"
                :key="control.id"
                v-model="control.configuration.Menu.value"
                :items="control.configuration.Menu.options"
                item-text="name"
                item-value="value"
                :label="control.name"
                :disabled="!isActive(control)"
                @change="updateControlsValues([control])"
              />
              <v-checkbox
                v-for="control in bool_controls"
                :key="control.id"
                v-model="control.configuration.Bool.value"
                :label="control.name"
                :disabled="!isActive(control)"
                @change="updateControlsValues([control])"
              />
              <div class="d-flex mt-5">
                <v-btn
                  color="primary"
                  @click="showDialog(false)"
                >
                  Close
                </v-btn>
                <v-spacer />
                <v-btn
                  color="primary"
                  @click="restoreDefaultValues"
                >
                  Restore defaults
                </v-btn>
              </div>
            </v-container>
            <v-container v-else>
              No controllers available for this device.
            </v-container>
          </v-card-text>
        </v-col>
        <v-col cols="4">
          <video-thumbnail
            v-if="$vuetify.breakpoint.smAndUp && are_controllers_available"
            height="auto"
            width="280"
            :source="device.source"
            style="position: sticky; top: 100px"
          />
        </v-col>
      </v-layout>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import Notifier from '@/libs/notifier'
import video from '@/store/video'
import { video_manager_service } from '@/types/frontend_services'
import {
  Bool, Control, Device, Menu, Slider,
} from '@/types/video'
import back_axios from '@/utils/api'

import VideoThumbnail from './VideoThumbnail.vue'

const notifier = new Notifier(video_manager_service)

export default Vue.extend({
  name: 'VideoControlsDialog',
  components: {
    VideoThumbnail,
  },
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    device: {
      type: Object as PropType<Device>,
      required: true,
    },
  },
  computed: {
    are_controllers_available(): boolean {
      return !this.device.controls.isEmpty()
    },
    menu_controls(): Menu[] {
      return this.device.controls.filter((control): control is Menu => 'Menu' in control.configuration)
    },
    bool_controls(): Bool[] {
      return this.device.controls.filter((control): control is Bool => 'Bool' in control.configuration)
    },
    slider_controls(): Slider[] {
      return this.device.controls.filter((control): control is Slider => 'Slider' in control.configuration)
    },
  },
  methods: {
    async restoreDefaultValues(): Promise<void> {
      const updated_controls: Control[] = []
      for (const control of this.device.controls) {
        if (!this.isActive(control)) {
          continue
        }
        const conf = control.configuration
        if ('Menu' in conf && conf.Menu.value !== conf.Menu.default) {
          conf.Menu.value = conf.Menu.default
        } else if ('Bool' in conf && conf.Bool.value !== conf.Bool.default) {
          conf.Bool.value = conf.Bool.default
        } else if ('Slider' in conf && conf.Slider.value !== conf.Slider.default) {
          conf.Slider.value = conf.Slider.default
        }
        updated_controls.push(control)
      }
      await this.updateControlsValues(updated_controls)
    },
    async updateControlsValues(controls: Control[]): Promise<void> {
      for await (const control of controls) {
        let value = 0
        if ('Menu' in control.configuration) {
          value = control.configuration.Menu.value
        } else if ('Bool' in control.configuration) {
          value = control.configuration.Bool.value ? 1 : 0
        } else if ('Slider' in control.configuration) {
          value = control.configuration.Slider.value
        }

        back_axios({
          method: 'post',
          url: `${video.API_URL}/v4l`,
          timeout: 10000,
          data: {
            device: this.device.source,
            v4l_id: control.id,
            value,
          },
        }).catch((error) => {
          const message = `Could not update value on ${control.name} control: ${error}.`
          notifier.pushError('CONTROL_VALUE_UPDATE_FAIL', message)
        })
      }

      video.fetchDevices()
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
    isActive(control: Control): boolean {
      return !(control.state.is_disabled || control.state.is_inactive)
    },
  },
})
</script>
