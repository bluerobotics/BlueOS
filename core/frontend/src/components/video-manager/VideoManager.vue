<template>
  <v-card
    elevation="0"
    class="video-manager"
  >
    <div
      v-if="!has_device_fetch_error && are_video_devices_available && !updating_devices"
      class="videos-list"
    >
      <video-diagnostic-helper />
      <template
        v-for="(device, index) in video_devices"
      >
        <v-divider
          v-if="index !== 0"
          :key="index"
        />
        <video-device
          :key="device.source"
          :device="device"
        />
      </template>
    </div>
    <spinning-logo
      v-else-if="!has_device_fetch_error && updating_devices"
      size="30%"
      subtitle="Fetching available video devices..."
    />
    <v-card
      v-else
      class="mx-auto my-12 pa-8 text-h6 text-center"
      width="300"
    >
      {{ has_device_fetch_error ? fetch_devices_error : 'No video-devices available.' }}
    </v-card>
    <video-updater />

    <v-fab-transition>
      <v-btn
        :key="'create_button'"
        color="primary"
        fab
        large
        dark
        fixed
        bottom
        right
        class="v-btn--example"
        @click="openSettingsDialog"
      >
        <v-icon>mdi-cog</v-icon>
      </v-btn>
    </v-fab-transition>

    <v-dialog
      width="500"
      :value="show_settings_dialog"
      @input="show_settings_dialog = false"
    >
      <v-card>
        <v-card-title>
          Video Manager Settings
        </v-card-title>

        <v-card-actions class="d-flex flex-column justify-space-around align-center pb-6">
          <v-switch
            v-model="legacy_mode"
            label="Raspberry legacy camera support"
            @change="toggleLegacyMode"
          />
          <v-btn
            @click="resetSettings"
          >
            <v-icon left>
              mdi-cog-refresh
            </v-icon>
            Reset Settings
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import commander from '@/store/commander'
import video from '@/store/video'
import { commander_service } from '@/types/frontend_services'
import {
  Device, Format, StreamStatus, VideoEncodeType, VideoSourceRedirect,
} from '@/types/video'

import VideoDevice from './VideoDevice.vue'
import VideoDiagnosticHelper from './VideoDiagnosticHelper.vue'
import VideoUpdater from './VideoUpdater.vue'

const notifier = new Notifier(commander_service)

export default Vue.extend({
  name: 'VideoManager',
  components: {
    VideoDevice,
    VideoUpdater,
    SpinningLogo,
    VideoDiagnosticHelper,
  },
  data() {
    return {
      show_settings_dialog: false,
      legacy_mode: false,
    }
  },
  computed: {
    video_streams(): StreamStatus[] {
      return video.available_streams
    },
    are_video_devices_available(): boolean {
      return !this.video_devices.isEmpty()
    },
    video_devices(): Device[] {
      function has_supported_encode(device: Device): boolean {
        if (settings.is_pirate_mode) {
          return true
        }
        return device.formats.some((format: Format) => format.encode === VideoEncodeType.H264)
      }

      const has_active_stream = (device: Device): boolean => this.video_streams.some((stream) => {
        if ('Gst' in stream.video_and_stream.video_source) {
          return stream.video_and_stream.video_source.Gst.source.Fake === device.source
        }
        if ('Local' in stream.video_and_stream.video_source) {
          return stream.video_and_stream.video_source.Local.device_path === device.source
        }
        if ('Redirect' in stream.video_and_stream.video_source) {
          // eslint-disable-next-line no-extra-parens
          return (stream.video_and_stream.video_source.Redirect as VideoSourceRedirect)
            .source.Redirect === device.source
        }
        return false
      })

      function should_show(device: Device): boolean {
        if (device.name === 'Fake source') {
          return has_active_stream(device) || settings.is_pirate_mode
        }
        return true
      }

      return video.available_devices
        .filter(
          (device) => has_supported_encode(device) || has_active_stream(device) || this.is_redirect_source(device),
        )
        .filter(should_show)
        .sort((a: Device, b: Device) => a.name.localeCompare(b.name))
    },
    updating_devices(): boolean {
      return video.updating_devices
    },
    fetch_devices_error(): string | null {
      return video.fetch_devices_error
    },
    has_device_fetch_error(): boolean {
      return this.fetch_devices_error !== null
    },
  },
  async mounted() {
    await this.updateCameraLegacy()
  },
  methods: {
    async updateCameraLegacy(): Promise<void> {
      this.legacy_mode = await commander.getRaspiCameraLegacy() === true
    },
    async setCameraLegacy(enable: boolean): Promise<void> {
      await commander.setRaspiCameraLegacy(enable)
        .then(() => {
          const message = 'Reboot is required for this action to take effect.'
          notifier.pushInfo('DO_CAMERA_LEGACY_REBOOT_REQUIRED', message, true)
        })
    },
    async toggleLegacyMode(): Promise<void> {
      await this.setCameraLegacy(this.legacy_mode)
    },
    is_redirect_source(device: Device): boolean {
      return device.source === 'Redirect'
    },
    openSettingsDialog(): void {
      this.show_settings_dialog = true
    },
    resetSettings(): void {
      video.resetSettings()
      this.show_settings_dialog = false
    },
  },
})
</script>

<style scoped>
.video-manager {
  max-width: 700px;
  margin: auto;
  background-color: transparent;
}
.videos-list {
  margin: 30px 15px;
  background-color: transparent;
}
</style>
