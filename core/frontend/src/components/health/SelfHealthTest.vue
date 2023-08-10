<template>
  <v-container>
    <v-row
      class="mb-6 mt-6"
      justify="center"
      no-gutters
    >
      <v-alert
        v-if="is_running_factory"
        border="top"
        colored-border
        type="warning"
        elevation="2"
        dismissible
      >
        This vehicle is running its "factory" version of BlueOS.
        This generally means something went wrong, and the system reverted to this version
        in order to recover.
        Please file an issue at <a
          href="https://github.com/bluerobotics/BlueOS/issues"
          target="_blank"
        >BlueOS/issues</a>
        or post on our <a
          href="https://discuss.bluerobotics.com/c/bluerobotics-software/blue-os/85"
          target="_blank"
        >forum</a>.
        Please include the <a href="#" @click="downloadLogs()">System logs</a>
        if possible, and what you were doing when this happened.
      </v-alert>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import filebrowser from '@/libs/filebrowser'
import * as VCU from '@/utils/version_chooser'

export default Vue.extend({
  name: 'SelfHealthTest',
  data: () => ({
    is_running_factory: false,
  }),
  async mounted() {
    await VCU.loadCurrentVersion()
      .then((image) => {
        if (image.tag === 'factory') {
          this.is_running_factory = true
        }
      })
  },
  methods: {
    async downloadLogs(): Promise<void> {
      const folder = await filebrowser.fetchFolder('system_logs')
      await filebrowser.downloadFolder(folder)
    },
  },
})
</script>
