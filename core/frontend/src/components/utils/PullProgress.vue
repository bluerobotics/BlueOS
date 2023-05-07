<template>
  <v-dialog
    :value="show"
    width="auto"
    persistent
  >
    <v-card
      min-width="450"
    >
      <v-card-title class="text-h5 grey lighten-2 black--text">
        Pulling new version
      </v-card-title>

      <v-card-text>
        <v-progress-linear
          :buffer-value="download"
          :value="extraction"
          stream
          class="mt-5 mb-5"
          color="blue"
          height="20"
        >
          <template #default>
            <strong
              v-if="download > 0 && download < 100"
            >
              Downloading: {{ download.toFixed(1) }}%
            </strong>
            <strong
              v-if="extraction > 0.1 && extraction < 100"
              class="ml-5"
            >
              Extracting: {{ extraction.toFixed(1) }}%
            </strong>
          </template>
        </v-progress-linear>
        <v-expansion-panels flat>
          <v-expansion-panel>
            <v-expansion-panel-header>
              Details
            </v-expansion-panel-header>
            <v-expansion-panel-content>
              <p
                style="white-space: pre; font-family:monospace;"
              >
                {{ progress }}
                {{ statustext }}
              </p>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>
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
    download: {
      type: Number,
      required: true,
    },
    extraction: {
      type: Number,
      required: true,
    },
    statustext: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
    }
  },
})
</script>
