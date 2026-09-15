<template>
  <div>
    <v-progress-circular
      v-if="loading"
      indeterminate
      size="24"
      color="primary"
    />
    <div v-else-if="notes">
      <!-- Rendered and sanitized by GitHub itself, which is what the release page serves -->
      <!-- eslint-disable vue/no-v-html -->
      <div
        class="release-notes"
        v-html="notes.html"
      />
      <!-- eslint-enable vue/no-v-html -->
    </div>
    <p
      v-else
      class="text-caption text--secondary ma-0"
    >
      Release notes are not available for this version.
    </p>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import { ReleaseNotes } from '@/types/version-chooser'
import { getReleaseNotes } from '@/utils/version_chooser'

export default Vue.extend({
  name: 'ReleaseNotes',
  props: {
    repository: {
      type: String,
      required: true,
    },
    tag: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      notes: undefined as (undefined | ReleaseNotes),
      loading: true,
    }
  },
  async mounted() {
    this.notes = await getReleaseNotes(this.repository, this.tag)
    this.loading = false
  },
})
</script>

<style scoped>
.release-notes ::v-deep h1,
.release-notes ::v-deep h2,
.release-notes ::v-deep h3 {
  font-size: 1.1rem;
  margin-top: 10px;
}

.release-notes ::v-deep ul {
  margin-bottom: 10px;
}
</style>
