<template>
  <v-row justify="space-around">
    <v-col cols="auto">
      <v-dialog
        v-model="should_open"
        transition="dialog-top-transition"
        max-width="600"
      >
        <template #default="dialog">
          <v-card>
            <v-toolbar
              color="primary"
              dark
            >
              <div class="text-h4">
                A new version is available!
              </div>
            </v-toolbar>
            <v-card-actions class="justify-center">
              <v-btn
                text
                elevation="2"
                x-large
                dialog.value
                href="/tools/version-chooser"
              >
                Update to {{ latest_version && latest_version.tag }}
              </v-btn>
            </v-card-actions>
            <v-card-actions class="justify-end">
              <v-btn
                text
                @click="dialog.value = false"
              >
                Close
              </v-btn>
            </v-card-actions>
          </v-card>
        </template>
      </v-dialog>
    </v-col>
  </v-row>
</template>
<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'
import { Version, VersionsQuery } from '@/types/version-chooser'
import * as VCU from '@/utils/version_chooser'

export default Vue.extend({
  name: 'UpdateTime',
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
          this.available_versions = VCU.sortImages(this.available_versions)
          this.latest_beta = VCU.getLatestBeta(this.available_versions)
          this.latest_stable = VCU.getLatestStable(this.available_versions)
          if (this.current_version) {
            this.latest_version = VCU.getLatestVersion(this.available_versions, this.current_version)
          }
          const milliseconds_diff = Date.now() - settings.last_version_update_notification_time.getTime()
          const minutes_diff = milliseconds_diff / (60 * 1000)
          if (minutes_diff > 10) {
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
