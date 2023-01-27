<template>
  <v-tooltip
    :top="position === 'top'"
    :right="position === 'right'"
    :bottom="position === 'bottom'"
    :left="position === 'left'"
    :activator="activator"
  >
    <span>{{ content }}</span>
  </v-tooltip>
</template>

<script>
import Vue from 'vue'

export default Vue.extend({
  name: 'DefaultTooltip',
  props: {
    // eslint-disable-next-line
    activator: { required: true },
    content: { type: String, required: true },
    position: { type: String, required: false, default: 'bottom' },
  },
})
</script>
