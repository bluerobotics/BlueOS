<template>
  <v-container>
    <v-row
      class="mb-6 mt-6"
      justify="center"
      no-gutters
    >
      <v-alert
        v-if="rolled_back"
        border="top"
        colored-border
        type="warning"
        elevation="2"
        dismissible
        @click="onWarningClick"
      >
        <!-- eslint-disable-next-line vue/no-v-html, max-len -->
        <span v-html="t`The last BlueOS update did not become healthy, so the vehicle returned to ${current_version} by itself. The failed version is still installed and can be inspected in the <a href='/tools/version-chooser'>version chooser</a>. Please file an issue at <a href='https://github.com/bluerobotics/BlueOS/issues' target='_blank'>BlueOS/issues</a> or post on our <a href='https://discuss.bluerobotics.com/c/bluerobotics-software/blue-os/85' target='_blank'>forum</a>. Please include the <a href='#' class='js-download-logs'>System logs</a> if possible.`" />
      </v-alert>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import commander from '@/store/commander'
import * as VCU from '@/utils/version_chooser_nixos'

export default Vue.extend({
  name: 'SelfHealthTestNixos',
  data: () => ({
    rolled_back: false,
    current_version: '',
  }),
  async mounted() {
    await VCU.loadStatus()
      .then((status) => {
        // A rollback is the NixOS equivalent of the factory-version fallback: the
        // system is running something older than what was asked for.
        this.rolled_back = status.rolled_back_from !== null
        this.current_version = status.current.version
      })
      .catch(() => { /* the version chooser shows an unreachable daemon */ })
  },
  methods: {
    downloadLogs(): void {
      window.open(`${commander.API_URL}/services/download_system_logs`, '_blank')
    },
    onWarningClick(event: MouseEvent): void {
      const target = event.target as HTMLElement | null
      if (target?.closest('.js-download-logs')) {
        event.preventDefault()
        this.downloadLogs()
      }
    },
  },
})
</script>
