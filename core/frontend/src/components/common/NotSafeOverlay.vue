<template>
  <v-overlay
    v-if="!is_safe"
    :absolute="true"
    :opacity="0.85"
  >
    <div class="d-flex flex-column justify-center align-center">
      <p class="text-center">
        This feature is disabled because the vehicle is armed.
      </p>
      <v-btn
        class="ml-auto mr-auto"
        color="warning"
        @click="override()"
      >
        I know what I'm doing, let me through
      </v-btn>
    </div>
  </v-overlay>
</template>

<script lang="ts">
import autopilot_data from '@/store/autopilot'

export default {
  name: 'NotSafeOverlay',
  data() {
    return {
      user_override: false,
    }
  },
  computed: {
    is_safe(): boolean {
      return autopilot_data.is_safe || this.user_override
    },
  },
  methods: {
    override() {
      this.user_override = true
    },
  },
}
</script>
