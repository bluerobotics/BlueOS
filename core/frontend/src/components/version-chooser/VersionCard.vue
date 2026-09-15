<template>
  <v-sheet
    class="my-4 pa-4 py-sm-0"
    :elevation="$vuetify.breakpoint.xs ? 1 : 0"
  >
    <div class="d-flex flex-column align-center flex-sm-row">
      <div class="d-flex">
        <v-list-item-avatar>
          <v-icon :class="current ? 'green' : 'grey'">
            {{ remote ? 'mdi-earth' : '' }}
            {{ current ? 'mdi-checkbox-blank-circle' : 'mdi-checkbox-blank-circle-outline' }}
          </v-icon>
        </v-list-item-avatar>

        <div>
          <p
            class="text-body-1 ma-0"
            v-text="image.tag"
          />
          <p
            v-if="settings.is_pirate_mode"
            class="text-caption text--secondary ma-0"
            v-text="`${image.sha ? shortSha(image.sha) : 'N/A'} - ${asTimeAgo(image.last_modified)}`"
          />
          <p
            v-else
            class="text-caption text--secondary ma-0"
            v-text="`${asTimeAgo(image.last_modified)}`"
          />
          <p
            class="text-caption text--secondary ma-0"
            v-text="image.repository"
          />
        </div>
      </div>
      <v-spacer />
      <div class="d-flex flex-wrap justify-center align-center my-2">
        <v-btn
          v-if="showDocsLink"
          v-tooltip="'Documentation for this version'"
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
          What's new?
        </v-btn>
        <v-alert
          v-if="upToDate && !settings.is_pirate_mode"
          class="mx-2 my-1"
          dense
          text
          type="success"
        >
          Up to date
        </v-alert>
        <v-alert
          v-if="settings.is_pirate_mode && current"
          class="mx-2 my-1"
          dense
          text
          type="success"
        >
          Running
        </v-alert>
        <div v-if="working">
          <spinning-logo
            size="30px"
          />
        </div>
        <v-btn
          v-if="newStableAvailable"
          color="primary"
          class="mx-2 my-1"
          @click="$emit('pull-and-apply', `${image.repository}:${newStableAvailable}`)"
          v-text="`Upgrade to ${newStableAvailable}`"
        />
        <v-btn
          v-if="current && updateAvailable"
          color="primary"
          class="mx-2 my-1 scroll-container"
          width="195"
          :disabled="working"
          @click="$emit('pull-and-apply', `${image.repository}:${image.tag}`)"
        >
          <div class="scroll-text">
            Update to latest {{ image.tag }}
          </div>
        </v-btn>
        <v-dialog
          v-model="bootstrapDialog"
          width="500"
        >
          <template #activator="{ on, attrs }">
            <v-btn
              v-if="showBootstrapUpdate"
              color="warning"
              class="mx-2 my-1"
              :disabled="working"
              dark
              v-bind="attrs"
              v-on="on"
            >
              Update Bootstrap
            </v-btn>
          </template>

          <v-card>
            <v-card-title
              class="text-h5 lighten-2"
            >
              Info
            </v-card-title>

            <v-card-text class="text-h6 text-center mt-6">
              Updating bootstrap is only recommended between stable versions.
            </v-card-text>

            <v-divider />

            <v-card-actions>
              <v-btn
                color="primary"
                @click="bootstrapDialog = false"
              >
                Abort
              </v-btn>
              <v-spacer />
              <v-btn
                color="primary"
                @click="updateBootstrap"
              >
                Update
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
        <v-btn
          v-if="newBetaAvailable"
          color="primary"
          class="mx-2 my-1"
          :disabled="working"
          @click="$emit('pull-and-apply', `${image.repository}:${newBetaAvailable}`)"
          v-text="`Upgrade to ${newBetaAvailable}`"
        />
        <v-btn
          v-if="!current && !remote && imageCanBeDeleted()"
          color="error"
          class="mx-2 my-1"
          :disabled="working"
          @click="$emit('delete', `${image.repository}:${image.tag}`)"
          v-text="'Delete'"
        />
        <v-btn
          v-if="!current && !remote"
          color="primary"
          class="mx-2 my-1"
          :disabled="working"
          @click="$emit('apply', `${image.repository}:${image.tag}`)"
          v-text="'Apply'"
        />
        <v-btn
          v-if="showPullButton"
          color="primary"
          class="mx-2 my-1"
          :disabled="working"
          @click="$emit('pull-and-apply', `${image.repository}:${image.tag}`)"
          v-text="'Download and Apply'"
        />
        <v-btn
          v-if="showReleaseNotes && notesExpanded"
          key="hide-notes"
          v-tooltip="'Hide release notes'"
          icon
          @click="notesExpanded = false"
        >
          <v-icon>mdi-chevron-up</v-icon>
        </v-btn>
      </div>
    </div>
    <release-notes
      v-if="showReleaseNotes && notesExpanded"
      :key="image.tag"
      class="pb-4"
      :repository="image.repository"
      :tag="image.tag"
    />
  </v-sheet>
</template>

<script lang="ts">
import TimeAgo from 'javascript-time-ago'
import en from 'javascript-time-ago/locale/en.json'
import Vue, { PropType } from 'vue'

import settings from '@/libs/settings'
import helper from '@/store/helper'
import { Dictionary } from '@/types/common'
import { InternetConnectionState } from '@/types/helper'
import {
  DEFAULT_REMOTE_IMAGE, getDocsUrl, isSemVer,
} from '@/utils/version_chooser'

import SpinningLogo from '../common/SpinningLogo.vue'
import ReleaseNotes from './ReleaseNotes.vue'

TimeAgo.addDefaultLocale(en)
const timeAgo = new TimeAgo('en-US')

export default Vue.extend({
  name: 'VersionCard',
  components: {
    ReleaseNotes,
    SpinningLogo,
  },
  props: {
    current: {
      type: Boolean,
      default: false,
    },
    bootstrapVersion: {
      type: String as PropType<string | undefined>,
      default: undefined,
    },
    latestStable: {
      type: String as PropType<string | undefined>,
      default: undefined,
    },
    upToDate: {
      type: Boolean,
      default: false,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    newStableAvailable: {
      type: String,
      default: '',
    },
    newBetaAvailable: {
      type: String,
      default: '',
    },
    updateAvailable: {
      type: Boolean,
      default: false,
    },
    image: {
      type: Object as PropType<Dictionary<string>>,
      default() { return {} },
    },
    remote: {
      type: Boolean,
      default: false,
    },
    showPullButton: {
      type: Boolean,
      default: false,
    },
    enableDelete: {
      type: Boolean,
      default: true,
    },
    deleting: {
      type: Boolean,
      default: false,
    },
    updating: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      bootstrapDialog: false,
      notesExpanded: false,
      settings,
    }
  },
  computed: {
    working(): boolean {
      return this.loading || this.deleting || this.updating
    },
    isFromBR(): boolean {
      return this.image.repository === DEFAULT_REMOTE_IMAGE
    },
    hasInternet(): boolean {
      return helper.has_internet !== InternetConnectionState.OFFLINE
        && helper.has_internet !== InternetConnectionState.UNKNOWN
    },
    showBootstrapUpdate(): boolean {
      if (!this.bootstrapVersion || !this.hasInternet) {
        return false
      }
      return this.settings.is_pirate_mode && this.current && !this.updateAvailable && this.isFromBR
        && this.bootstrapVersion !== `${this.image.repository.split('/')[0]}/blueos-bootstrap:${this.image.tag}`
    },
    showReleaseNotes(): boolean {
      return this.isFromBR && this.hasInternet && isSemVer(this.image.tag)
    },
    // Branch builds and custom tags are not documented anywhere, unlike releases and master
    showDocsLink(): boolean {
      return isSemVer(this.image.tag) || this.image.tag === 'master'
    },
    docsUrl(): string {
      return getDocsUrl(this.image.tag, this.latestStable)
    },
  },
  methods: {
    asTimeAgo(value: string) {
      return timeAgo.format(new Date(Date.parse(value)), 'round')
    },
    shortSha(value: string) {
      if (value === null) {
        return 'Unknown'
      }
      return value.replace('sha256:', '').substring(0, 8)
    },
    imageCanBeDeleted() {
      return (this.image.tag !== 'factory' || this.image.repository !== DEFAULT_REMOTE_IMAGE)
        && !this.deleting && this.enableDelete
    },
    updateBootstrap() {
      this.bootstrapDialog = false
      this.$emit('update-bootstrap', `bluerobotics/blueos-bootstrap:${this.image.tag}`)
    },
  },
})
</script>
