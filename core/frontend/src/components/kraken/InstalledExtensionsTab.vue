<template>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { ExtensionData } from '@/types/kraken'

export default Vue.extend({
  name: 'InstalledExtensionsTab',
  props: {
    extension: {
      type: Object as PropType<ExtensionData>,
      required: true,
    },
  },
})
</script>

<style scoped>

</style>
