<template>
  <v-container>
    <not-safe-overlay />
    <version-chooser />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import NotSafeOverlay from '@/components/common/NotSafeOverlay.vue'
import VersionChooser from '@/components/version-chooser/VersionChooser.vue'

export default Vue.extend({
  name: 'VersionChooserView',
  components: {
    VersionChooser,
    NotSafeOverlay,
  },
})
</script>
