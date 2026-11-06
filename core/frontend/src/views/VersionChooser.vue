<template>
  <v-container>
    <not-safe-overlay />
    <component :is="chooser" />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import NotSafeOverlay from '@/components/common/NotSafeOverlay.vue'
import VersionChooserDocker from '@/components/version-chooser/VersionChooser.vue'
import VersionChooserNixos from '@/components/version-chooser/VersionChooserNixos.vue'
import use_nixos_updates from '@/utils/updates_backend'

export default Vue.extend({
  name: 'VersionChooserView',
  components: {
    NotSafeOverlay,
  },
  data() {
    return {
      chooser: use_nixos_updates ? VersionChooserNixos : VersionChooserDocker,
    }
  },
})
</script>
