<template>
  <div>HEI</div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { ExtensionData } from '@/types/kraken'

export default Vue.extend({
  name: 'PublicStoreTab',
  props: {
    extension: {
      type: Object as PropType<ExtensionData>,
      required: true,
    },
  },
  computed: {
    isCompatible(): boolean {
      return this.extension.is_compatible ?? true
    },
  },
})
</script>

<style scoped>

</style>
