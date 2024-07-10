<template>
  <spinning-logo
    v-if="!params_finished_loaded"
    size="20%"
    :subtitle="subtitle"
  />
  <div v-else>
    <slot />
  </div>
</template>
<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'

export default Vue.extend({
  name: 'ParameterLoadingSpinner',
  components: {
    SpinningLogo,
  },

  computed: {
    subtitle(): string {
      if (this.rebooting) {
        return 'Rebooting autopilot'
      }
      return `${this.loaded_params}/${this.total_params} parameters loaded`
    },
    rebooting(): boolean {
      return autopilot.restarting
    },
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
