<template>
  <v-tooltip
    :top="position === 'top'"
    :right="position === 'right'"
    :bottom="position === 'bottom'"
    :left="position === 'left'"
    :activator="activator"
  >
    <span>{{ pirate_prefix }}{{ content }}</span>
  </v-tooltip>
</template>

<script>
import Vue from 'vue'

import settings from '@/libs/settings'

export default Vue.extend({
  name: 'DefaultTooltip',
  props: {
    activator: { required: true }, // eslint-disable
    content: { type: String, required: true },
    position: { type: String, required: false, default: 'bottom' },
  },
  data() {
    return {
      settings,
    }
  },
  computed: {
    pirate_prefix() {
      return this.settings.is_pirate_mode ? 'Arrrgh! ' : ''
    },
  },
})
</script>
