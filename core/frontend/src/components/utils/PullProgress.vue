<template>
  <v-dialog
    :value="show"
    width="auto"
    persistent
  >
    <v-card
      min-width="450"
      :data-testid="testId"
    >
      <v-card-title class="text-h5 grey lighten-2 black--text">
        {{ t`Pulling new version` }}
      </v-card-title>

      <v-card-text>
        <p
          v-if="step !== ''"
          class="text-subtitle-2 mb-1 mt-3"
          :data-testid="`${testId}-step`"
        >
          {{ step }}
        </p>
        <v-progress-linear
          :buffer-value="download"
          :value="extraction"
          stream
          class="mt-5 mb-5"
          color="blue"
          height="20"
          :data-testid="`${testId}-bar`"
        >
          <template #default>
            <strong
              v-if="download > 0 && download < 100"
            >
              {{ t`Downloading: ${download.toFixed(1)}%` }}
            </strong>
            <strong
              v-if="extraction > 0.1 && extraction < 100"
              class="ml-5"
            >
              {{ t`Extracting: ${extraction.toFixed(1)}%` }}
            </strong>
          </template>
        </v-progress-linear>
        <v-expansion-panels flat>
          <v-expansion-panel>
            <v-expansion-panel-header>
              {{ t`Details` }}
            </v-expansion-panel-header>
            <v-expansion-panel-content>
              <p
                style="white-space: pre; font-family:monospace;"
                :data-testid="`${testId}-details`"
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
    step: {
      type: String,
      default: '',
    },
    testId: {
      type: String,
      default: 'pull-progress',
    },
  },
  data() {
    return {
    }
  },
})
</script>
