<template>
  <v-list-item>
    <v-list-item-avatar>
      <v-icon
        :class="current ? 'green' : 'grey'"
      >
        {{ remote? 'mdi-earth' : '' }}
        {{ current? 'mdi-checkbox-blank-circle' : 'mdi-checkbox-blank-circle-outline' }}
      </v-icon>
    </v-list-item-avatar>

    <v-list-item-content>
      <v-list-item-title v-text="image.tag" />
      <v-list-item-subtitle
        v-if="settings.is_pirate_mode"
        v-text="`${image.sha? shortSha(image.sha) : 'N/A'} - ${asTimeAgo(image.last_modified)}`"
      />
      <v-list-item-subtitle
        v-else
        v-text="`${asTimeAgo(image.last_modified)}`"
      />
      <v-list-item-subtitle v-text="image.repository" />
    </v-list-item-content>
    <v-list-item-action>
      <v-alert
        v-if="upToDate && !settings.is_pirate_mode"
        dense
        text
        type="success"
      >
        Up to date
      </v-alert>
      <v-alert
        v-if="settings.is_pirate_mode && current"
        dense
        text
        type="success"
      >
        Running
      </v-alert>
    </v-list-item-action>
    <v-list-item-action v-if="loading || deleting">
      <spinning-logo
        style="max-width:10%"
        size="10%"
        :subtitle="loading ? 'Loading image...' : 'Deleting image...'"
      />
    </v-list-item-action>
    <v-list-item-action v-if="newStableAvailable">
      <v-btn
        color="primary"
        class="mr-2 mb-4"
        @click="$emit('pull-and-apply',`${image.repository}:${newStableAvailable}`)"
        v-text="`Upgrade to ${newStableAvailable}`"
      />
    </v-list-item-action>
    <v-list-item-action v-if="current && updateAvailable">
      <v-btn
        color="primary"
        class="mr-2 mb-4"
        @click="$emit('pull-and-apply',`${image.repository}:${image.tag}`)"
        v-text="`Update to latest ${image.tag}`"
      />
    </v-list-item-action>
    <v-list-item-action v-if="newBetaAvailable">
      <v-btn
        color="primary"
        class="mr-2 mb-4"
        @click="$emit('pull-and-apply',`${image.repository}:${newBetaAvailable}`)"
        v-text="`Upgrade to ${newBetaAvailable}`"
      />
    </v-list-item-action>
    <v-list-item-action v-if="!current && !remote && imageCanBeDeleted()">
      <v-btn
        color="error"
        class="mr-2 mb-4"
        @click="$emit('delete', `${image.repository}:${image.tag}`)"
        v-text="'Delete'"
      />
    </v-list-item-action>
    <v-list-item-action v-if="!current && !remote">
      <v-btn
        color="primary"
        class="mr-2 mb-4"
        @click="$emit('apply',`${image.repository}:${image.tag}`)"
        v-text="'Apply'"
      />
    </v-list-item-action>
    <v-list-item-action v-if="showPullButton">
      <v-btn
        color="primary"
        class="mr-2 mb-4"
        @click="$emit('pull-and-apply', `${image.repository}:${image.tag}`)"
        v-text="'Download and Apply'"
      />
    </v-list-item-action>
  </v-list-item>
</template>

<script lang="ts">
import TimeAgo from 'javascript-time-ago'
import en from 'javascript-time-ago/locale/en.json'
import Vue, { PropType } from 'vue'

import settings from '@/libs/settings'
import { Dictionary } from '@/types/common'
import { DEFAULT_REMOTE_IMAGE } from '@/utils/version_chooser'

import SpinningLogo from '../common/SpinningLogo.vue'

TimeAgo.addDefaultLocale(en)
const timeAgo = new TimeAgo('en-US')

export default Vue.extend({
  name: 'VersionCard',
  components: {
    SpinningLogo,
  },
  props: {
    current: {
      type: Boolean,
      default: false,
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
    deleting: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      settings,
    }
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
      return this.image.tag !== 'factory' || this.image.repository !== DEFAULT_REMOTE_IMAGE
    },
  },
})
</script>
