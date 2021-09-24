<template>
  <v-dialog
    width="500"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        Video configuration
      </v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-container v-if="are_controllers_available">
          <v-slider
            v-for="control in slider_controls"
            :key="control.id"
            v-model="control.configuration.Slider.value"
            :min="control.configuration.Slider.min"
            :max="control.configuration.Slider.max"
            :step="control.configuration.Slider.step"
            :label="control.name"
            @change="updateControlValue(control)"
          />
          <v-select
            v-for="control in menu_controls"
            :key="control.id"
            v-model="control.configuration.Menu.value"
            :items="control.configuration.Menu.options"
            item-text="name"
            item-value="value"
            :label="control.name"
            @change="updateControlValue(control)"
          />
          <v-checkbox
            v-for="control in bool_controls"
            :key="control.id"
            v-model="control.configuration.Bool.value"
            :label="control.name"
            @change="updateControlValue(control)"
          />
          <div class="d-flex">
            <v-spacer />
            <v-btn
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
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import axios from 'axios'
import Vue, { PropType } from 'vue'
import { getModule } from 'vuex-module-decorators'

import NotificationStore from '@/store/notifications'
import VideoStore from '@/store/video'
import { video_manager_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import {
  Bool, Control, Device, Menu, Slider,
} from '@/types/video'

const video_store: VideoStore = getModule(VideoStore)
const notification_store: NotificationStore = getModule(NotificationStore)

export default Vue.extend({
  name: 'VideoControlsDialog',
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
      return this.device.controls.length !== 0
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
      for (const control of this.device.controls) {
        const conf = control.configuration
        if ('Menu' in conf && conf.Menu.value !== conf.Menu.default) {
          conf.Menu.value = conf.Menu.default
        } else if ('Bool' in conf && conf.Bool.value !== conf.Bool.default) {
          conf.Bool.value = conf.Bool.default
        } else if ('Slider' in conf && conf.Slider.value !== conf.Slider.default) {
          conf.Slider.value = conf.Slider.default
        }
        await this.updateControlValue(control)
      }
    },
    async updateControlValue(control: Control): Promise<void> {
      let value = 0
      if ('Menu' in control.configuration) {
        value = control.configuration.Menu.value
      } else if ('Bool' in control.configuration) {
        value = control.configuration.Bool.value ? 1 : 0
      } else if ('Slider' in control.configuration) {
        value = control.configuration.Slider.value
      }

      await axios({
        method: 'post',
        url: `${video_store.API_URL}/v4l`,
        timeout: 10000,
        data: {
          device: this.device.source,
          v4l_id: control.id,
          value,
        },
      })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            video_manager_service,
            'CONTROL_VALUE_UPDATE_FAIL',
            `Could not update value on ${control.name} control: ${error}.`,
          ))
        })
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>
