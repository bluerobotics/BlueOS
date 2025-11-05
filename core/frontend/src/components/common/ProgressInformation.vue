<template>
  <v-container>
    <v-progress-linear
      indeterminate
      color="primary"
    />
    <div v-if="type === 'download'" class="mt-2">
      <div class="text-subtitle-2">
        {{ operation }}
      </div>
      <div class="text-caption">
        Size: {{ formatSize(currentSize / 1024) }}
      </div>
      <div class="text-caption">
        Total: {{ formatSize(totalSize / 1024) }}
      </div>
      <div class="text-caption">
        Speed: {{ formatSize(downloadSpeed / 1024) }}/s
      </div>
    </div>
    <div v-else-if="type === 'deletion'" class="mt-2">
      <div class="text-subtitle-2">
        Deleting: {{ currentPath }}
      </div>
      <div class="text-caption">
        Size: {{ formatSize(currentSize / 1024) }}
      </div>
      <div class="text-caption">
        Total: {{ formatSize(totalSize / 1024) }}
      </div>
      <div class="text-caption">
        Status: {{ status }}
      </div>
    </div>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import { prettifySize } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'ProgressInformation',
  props: {
    type: {
      type: String,
      required: true,
      validator: (value: string) => ['download', 'deletion'].includes(value),
    },
    operation: {
      type: String,
      required: false,
      default: '',
    },
    currentSize: {
      type: Number,
      required: true,
    },
    totalSize: {
      type: Number,
      required: true,
    },
    downloadSpeed: {
      type: Number,
      required: false,
      default: 0,
    },
    currentPath: {
      type: String,
      required: false,
      default: '',
    },
    status: {
      type: String,
      required: false,
      default: '',
    },
  },
  methods: {
    formatSize(kb_bytes: number): string {
      return prettifySize(kb_bytes)
    },
  },
})
</script>
