<template>
  <v-dialog
    v-model="should_open"
    transition="dialog-top-transition"
    width="fit-content"
    max-width="80%"
  >
    <v-card>
      <v-card-title class="justify-center pt-6">
        A new version is available!
      </v-card-title>
      <v-card-actions class="justify-center">
        <v-btn
          class="ma-6 elevation-2"
          x-large
          color="primary"
          href="/tools/version-chooser"
          @click="should_open = false"
        >
          Update to {{ latest_version && latest_version.tag }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'
import { Version, VersionsQuery } from '@/types/version-chooser'
import * as VCU from '@/utils/version_chooser'

export default Vue.extend({
  name: 'NewVersionNotificator',
  data() {
    return {
      available_versions: {
        local: [],
        remote: [],
        error: null,
      } as VersionsQuery,
      current_version: null as (null | Version),
      latest_beta: undefined as (undefined | Version),
      latest_stable: undefined as (undefined | Version),
      selected_image: 'bluerobotics/blueos-core',
      latest_version: undefined as (undefined | Version),
      should_open: false,
    }
  },
  mounted() {
    this.run()
  },
  methods: {
    latestVersion(): boolean {
      return this.latest_version !== undefined
        && this.current_version !== undefined
        && this.latest_version?.sha !== this.current_version?.sha
    },
    async run() {
      await VCU.loadCurrentVersion()
        .then((image) => {
          this.current_version = image
          this.selected_image = image.repository
        })

      await VCU.loadAvailableVersions(this.selected_image)
        .then((versions_query) => {
          this.available_versions = versions_query
        })
        .finally(() => {
          if (this.available_versions.error) {
            return
          }
          this.available_versions = VCU.sortImages(this.available_versions)
          this.latest_beta = VCU.getLatestBeta(this.available_versions)
          this.latest_stable = VCU.getLatestStable(this.available_versions)
          if (this.current_version) {
            this.latest_version = VCU.getLatestVersion(this.available_versions, this.current_version)
          }
          const milliseconds_diff = Date.now() - settings.last_version_update_notification_time.getTime()
          const days_diff = milliseconds_diff / (24 * 60 * 60 * 1000)
          if (days_diff > 1) {
            settings.updateVersionUpdateNotificationTime()
            this.should_open = this.latestVersion()
          }
        })
        .catch((error) => {
          this.available_versions = {
            local: [],
            remote: [],
            error: `Failed to communicate with backend: ${error}`,
          }
        })
    },
  },
})
</script>
