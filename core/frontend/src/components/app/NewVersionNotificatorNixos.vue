<template>
  <v-dialog
    v-model="should_open"
    transition="dialog-top-transition"
    width="fit-content"
    max-width="80%"
  >
    <v-card>
      <v-card-title class="justify-center pt-6">
        {{ t`A new version is available!` }}
      </v-card-title>
      <v-card-text
        v-if="show_release_notes"
        class="release-notes-preview"
      >
        <release-notes
          :key="latest_version?.version"
          :version="latest_version?.version ?? ''"
        />
      </v-card-text>
      <v-card-actions class="justify-center">
        <v-btn
          class="ma-6 elevation-2"
          x-large
          color="primary"
          href="/tools/version-chooser"
          @click="should_open = false"
        >
          {{ t`Update to ${latest_version && latest_version.version}` }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import ReleaseNotes from '@/components/version-chooser/ReleaseNotesNixos.vue'
import settings from '@/libs/settings'
import helper from '@/store/helper'
import { InternetConnectionState } from '@/types/helper'
import { Release } from '@/types/version-chooser-nixos'
import * as VCU from '@/utils/version_chooser_nixos'

export default Vue.extend({
  name: 'NewVersionNotificatorNixos',
  components: {
    ReleaseNotes,
  },
  data() {
    return {
      current_version: '',
      latest_version: undefined as (undefined | Release),
      should_open: false,
    }
  },
  computed: {
    can_fetch_remote(): boolean {
      return helper.has_internet === InternetConnectionState.ONLINE
        || helper.has_internet === InternetConnectionState.LIMITED
    },
    // A build with no release to point at would only be able to say the notes are unavailable
    show_release_notes(): boolean {
      return this.latest_version !== undefined && VCU.isSemVer(this.latest_version.version)
    },
  },
  watch: {
    can_fetch_remote() {
      this.run()
    },
  },
  mounted() {
    this.run()
  },
  methods: {
    /**
     * The manifest is the only source of "new version": a build that is not
     * published there is simply not offered, which is also true for a vehicle
     * updated by deploy-rs to something the publisher has not released.
     */
    async run() {
      await VCU.loadStatus()
        .then((status) => { this.current_version = status.current.version })
        .catch(() => { this.current_version = '' })

      if (!this.can_fetch_remote || this.current_version === '') {
        return
      }

      await VCU.loadReleases()
        .then((response) => {
          this.latest_version = VCU.getAvailableUpdate(this.current_version, response.releases)
          const milliseconds_diff = Date.now() - settings.last_version_update_notification_time.getTime()
          const days_diff = milliseconds_diff / (24 * 60 * 60 * 1000)
          if (days_diff > 1 && this.latest_version !== undefined) {
            settings.updateVersionUpdateNotificationTime()
            this.should_open = true
          }
        })
        .catch(() => { /* the version chooser reports an unreachable manifest */ })
    },
  },
})
</script>
