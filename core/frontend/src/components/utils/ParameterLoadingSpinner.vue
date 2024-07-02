<template>
  <spinning-logo
    v-if="!params_finished_loaded"
    size="20%"
    :subtitle="`${loaded_params}/${total_params} parameters loaded`"
  />
  <div v-else>
    <slot />
  </div>
</template>
<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import autopilot_data from '@/store/autopilot'

export default Vue.extend({
  name: 'ParameterLoadingSpinner',
  components: {
    SpinningLogo,
  },

  computed: {
    params_finished_loaded(): boolean {
      return autopilot_data.finished_loading
    },
    loaded_params(): number {
      return autopilot_data.parameters_loaded
    },
    total_params(): number {
      return autopilot_data.parameters_total
    },
  },
})
</script>
