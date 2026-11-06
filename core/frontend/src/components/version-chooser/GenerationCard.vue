<template>
  <v-sheet
    class="my-4 pa-4 py-sm-0"
    :elevation="$vuetify.breakpoint.xs ? 1 : 0"
  >
    <div class="d-flex flex-column align-center flex-sm-row">
      <div class="d-flex">
        <v-list-item-avatar>
          <v-icon :class="generation.current ? 'green' : 'grey'">
            {{ generation.current ? 'mdi-checkbox-blank-circle' : 'mdi-checkbox-blank-circle-outline' }}
          </v-icon>
        </v-list-item-avatar>

        <div>
          <p
            class="text-body-1 ma-0"
            v-text="generation.version"
          />
          <p
            class="text-caption text--secondary ma-0"
            v-text="generationSubtitle"
          />
          <p
            v-if="settings.is_pirate_mode"
            class="text-caption text--secondary ma-0"
            v-text="closureName"
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
          v-if="generation.current"
          class="mx-2 my-1"
          dense
          text
          type="success"
        >
          {{ t`Running` }}
        </v-alert>
        <v-alert
          v-else-if="generation.known_good"
          class="mx-2 my-1"
          dense
          text
          type="info"
        >
          {{ t`Rollback target` }}
        </v-alert>
        <v-btn
          v-if="!generation.current && settings.is_pirate_mode"
          color="secondary"
          class="mx-2 my-1"
          :disabled="working"
          :loading="working && activating"
          @click="$emit('activate', 'switch')"
          v-text="t`Switch to`"
        />
        <v-btn
          v-if="!generation.current"
          v-tooltip="t`Install it and reboot into it`"
          color="primary"
          class="mx-2 my-1"
          :disabled="working"
          :loading="working && activating"
          @click="$emit('activate', 'boot')"
          v-text="t`Boot into`"
        />
        <v-btn
          v-if="canDelete"
          color="error"
          class="mx-2 my-1"
          :disabled="working"
          :loading="working && deleting"
          @click="$emit('delete')"
          v-text="t`Delete`"
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
      :key="generation.version"
      class="pb-4"
      :version="generation.version"
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
import { Generation } from '@/types/version-chooser-nixos'
import { getDocsUrl, isSemVer } from '@/utils/version_chooser_nixos'

import ReleaseNotesNixos from './ReleaseNotesNixos.vue'

export default Vue.extend({
  name: 'GenerationCard',
  components: {
    ReleaseNotesNixos,
  },
  props: {
    generation: {
      type: Object as PropType<Generation>,
      required: true,
    },
    latestStable: {
      type: String,
      default: '',
    },
    activating: {
      type: Boolean,
      default: false,
    },
    deleting: {
      type: Boolean,
      default: false,
    },
    canDelete: {
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
      return this.activating || this.deleting
    },
    hasInternet(): boolean {
      return helper.has_internet !== InternetConnectionState.OFFLINE
        && helper.has_internet !== InternetConnectionState.UNKNOWN
    },
    // Branch builds and custom versions are not documented anywhere, unlike releases and master
    showDocsLink(): boolean {
      return isSemVer(this.generation.version) || this.generation.version === 'master'
    },
    docsUrl(): string {
      return getDocsUrl(this.generation.version, this.latestStable)
    },
    showReleaseNotes(): boolean {
      return this.hasInternet && isSemVer(this.generation.version)
    },
    /**
     * The store path is the identity of the build, which the version alone does
     * not give: two builds of one version are different generations.
     */
    closureName(): string {
      const name = this.generation.toplevel.split('/').pop() ?? ''
      return name.replace(/^[a-z0-9]{32}-/, '')
    },
    generationSubtitle(): string {
      const head = `${t`Generation`} ${this.generation.generation}`
      return `${head} - ${this.generation.channel} - ${this.asTimeAgo(this.generation.created)}`
    },
  },
  methods: {
    asTimeAgo(value: string): string {
      return `${formatDistanceToNow(new Date(Date.parse(value)))} ${t`ago`}`
    },
  },
})
</script>
