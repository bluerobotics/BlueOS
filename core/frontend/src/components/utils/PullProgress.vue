<template>
  <v-dialog
    :value="show"
    width="auto"
  >
    <v-card>
      <v-card-title class="text-h5 grey lighten-2 black--text">
        Pulling new version
      </v-card-title>

      <v-card-text>
        <p
          style="white-space: pre; font-family:monospace;"
        >
          {{ progress }}
        </p>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'PullProgress',
  props: {
    progress: {
      type: String,
      required: true,
    },
    show: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
    }
  },
})
</script>
