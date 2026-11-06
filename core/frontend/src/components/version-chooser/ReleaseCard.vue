<template>
  <v-sheet
    class="my-4 pa-4 py-sm-0"
    :elevation="$vuetify.breakpoint.xs ? 1 : 0"
  >
    <div class="d-flex flex-column align-center flex-sm-row">
      <div class="d-flex">
        <v-list-item-avatar>
          <v-icon class="grey">
            mdi-earth
          </v-icon>
        </v-list-item-avatar>

        <div>
          <p
            class="text-body-1 ma-0"
            v-text="release.version"
          />
          <p
            class="text-caption text--secondary ma-0"
            v-text="subtitle"
          />
          <p
            v-if="settings.is_pirate_mode"
            class="text-caption text--secondary ma-0"
            v-text="release.toplevel"
          />
        </div>
      </div>
      <v-spacer />
      <div class="d-flex flex-wrap justify-center align-center my-2">
        <v-btn
          v-if="showDocsLink"
          v-tooltip="t`Documentation for this version`"
          icon
          :href="docsUrl"
          target="_blank"
          rel="noopener noreferrer"
        >
          <v-icon>mdi-book-open-variant</v-icon>
        </v-btn>
        <v-btn
          v-if="showReleaseNotes && !notesExpanded"
          key="show-notes"
          class="mx-2 my-1"
          text
          @click="notesExpanded = true"
        >
          <v-icon left>
            mdi-list-box-outline
          </v-icon>
          {{ t`What's new?` }}
        </v-btn>
        <v-alert
          v-if="installed"
          class="mx-2 my-1"
          dense
          text
          type="success"
        >
          {{ t`Downloaded` }}
        </v-alert>
        <v-btn
          v-if="!installed && settings.is_pirate_mode"
          class="mx-2 my-1"
          text
          :disabled="working"
          :loading="downloading"
          @click="$emit('download')"
          v-text="t`Download only`"
        />
        <v-btn
          v-if="showUpgrade"
          color="primary"
          class="mx-2 my-1"
          :disabled="working"
          :loading="activating"
          @click="$emit('activate', 'boot')"
          v-text="`${t`Upgrade to`} ${release.version}`"
        />
        <v-btn
          v-if="showInstall"
          color="primary"
          class="mx-2 my-1"
          :disabled="working"
          :loading="activating"
          @click="$emit('activate', 'boot')"
          v-text="t`Download and install`"
        />
        <v-btn
          v-if="showReleaseNotes && notesExpanded"
          key="hide-notes"
          v-tooltip="t`Hide release notes`"
          icon
          @click="notesExpanded = false"
        >
          <v-icon>mdi-chevron-up</v-icon>
        </v-btn>
      </div>
    </div>
    <release-notes-nixos
      v-if="showReleaseNotes && notesExpanded"
      :key="release.version"
      class="pb-4"
      :version="release.version"
    />
  </v-sheet>
</template>

<script lang="ts">
import { formatDistanceToNow } from 'date-fns'
import { t } from 'ttag'
import Vue, { PropType } from 'vue'

import settings from '@/libs/settings'
import helper from '@/store/helper'
import { InternetConnectionState } from '@/types/helper'
import { Release } from '@/types/version-chooser-nixos'
import { getDocsUrl, isSemVer } from '@/utils/version_chooser_nixos'

import ReleaseNotesNixos from './ReleaseNotesNixos.vue'

export default Vue.extend({
  name: 'ReleaseCard',
  components: {
    ReleaseNotesNixos,
  },
  props: {
    release: {
      type: Object as PropType<Release>,
      required: true,
    },
    latestStable: {
      type: String,
      default: '',
    },
    /** Whether this exact closure is already in the local store. */
    installed: {
      type: Boolean,
      default: false,
    },
    /** Whether this is the newest release of its line, so it is worth offering. */
    upgrade: {
      type: Boolean,
      default: false,
    },
    activating: {
      type: Boolean,
      default: false,
    },
    downloading: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      settings,
      notesExpanded: false,
    }
  },
  computed: {
    working(): boolean {
      return this.activating || this.downloading
    },
    hasInternet(): boolean {
      return helper.has_internet !== InternetConnectionState.OFFLINE
        && helper.has_internet !== InternetConnectionState.UNKNOWN
    },
    showReleaseNotes(): boolean {
      return this.hasInternet && isSemVer(this.release.version)
    },
    showDocsLink(): boolean {
      return isSemVer(this.release.version) || this.release.version === 'master'
    },
    docsUrl(): string {
      return getDocsUrl(this.release.version, this.latestStable)
    },
    showUpgrade(): boolean {
      return this.upgrade && !this.installed
    },
    showInstall(): boolean {
      return !this.upgrade && !this.installed
    },
    subtitle(): string {
      const parts = [this.release.channel || t`published`]
      if (this.release.published) {
        parts.push(`${formatDistanceToNow(new Date(Date.parse(this.release.published)))} ${t`ago`}`)
      }
      if (this.release.revision) {
        parts.push(this.release.revision.slice(0, 7))
      }
      return parts.join(' - ')
    },
  },
})
</script>
