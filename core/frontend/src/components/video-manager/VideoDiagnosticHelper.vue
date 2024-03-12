<template>
  <v-container>
    <v-row
      class="mb-6 mt-6"
      justify="center"
      no-gutters
    >
      <v-alert
        v-if="!has_accessible_streams"
        border="top"
        colored-border
        type="warning"
        elevation="2"
        dismissible
      >
        It looks like there's no video stream accessible from your device's detected IP address ({{ user_ip_address }}).
        <span v-if="is_connected_to_wifi">
          That should be fine if you are using this wi-fi connection for something other than piloting.
        </span>
      </v-alert>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import beacon from '@/store/beacon'
import video from '@/store/video'
import { Domain, InterfaceType } from '@/types/beacon'

export default Vue.extend({
  name: 'VideoDiagnosticHelper',
  data: () => ({
  }),
  computed: {
    user_ip_address(): string {
      return beacon.client_ip_address
    },
    vehicle_ip_address(): string {
      return beacon.nginx_ip_address
    },
    all_streams(): string[] {
      return video.available_streams.map((x) => x.video_and_stream.stream_information.endpoints).flat(1)
    },
    has_accessible_rtsp_streams(): boolean {
      return !this.all_streams.filter((x) => x.toLowerCase().startsWith(`rtsp://${this.vehicle_ip_address}`)).isEmpty()
    },
    has_accessible_udp_streams(): boolean {
      return !this.all_streams.filter((x) => x.toLowerCase().startsWith(`udp://${this.user_ip_address}`)).isEmpty()
    },
    has_accessible_streams(): boolean {
      return this.has_accessible_rtsp_streams || this.has_accessible_udp_streams
    },
    wireless_interface_domains(): Domain[] {
      return beacon.available_domains.filter(
        (entry) => entry.interface_type === InterfaceType.WIFI || entry.interface_type === InterfaceType.HOTSPOT,
      )
    },
    is_connected_to_wifi(): boolean {
      return this.wireless_interface_domains.some((domain) => domain.ip === beacon.nginx_ip_address)
    },

  },
})
</script>
