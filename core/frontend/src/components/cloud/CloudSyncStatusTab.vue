<template>
  <v-container class="cloud-status-tab pa-4">
    <div class="mb-4">
      <div class="text-subtitle-1 font-weight-medium">
        {{ summaryMessage }}
      </div>
      <div class="text-caption text--secondary">
        {{ activeCount }} uploading • {{ pendingCount }} waiting
      </div>
      <v-btn
        class="mt-3"
        color="primary"
        elevation="2"
        :href="missionsUrl"
        target="_blank"
        rel="noopener noreferrer"
      >
        Go to My Missions
      </v-btn>
    </div>
    <section class="cloud-status-section">
      <div class="d-flex align-center justify-space-between mb-2">
        <span class="text-body-2 font-weight-medium">Cloud file sync</span>
        <v-chip
          small
          outlined
        >
          {{ items.length }}
        </v-chip>
      </div>
      <template v-if="items.length > 0">
        <v-list
          dense
          class="py-0"
        >
          <v-list-item
            v-for="item in items"
            :key="item.id"
            class="px-0"
          >
            <v-list-item-content class="pr-4">
              <v-list-item-title class="text-body-2">
                {{ getFileName(item.display_path || item.path) }}
              </v-list-item-title>
              <v-list-item-subtitle class="text-caption mb-1">
                <template v-if="item.status === 'uploading'">
                  {{ formatFileSize(item.sent || 0) }} / {{ formatFileSize(item.total || 0) }}
                </template>
                <template v-else-if="item.status === 'pending'">
                  Waiting to upload • {{ formatFileSize(item.size) }}
                </template>
                <template v-else>
                  Completed • {{ formatFileSize(item.size) }}
                </template>
              </v-list-item-subtitle>
              <v-progress-linear
                v-if="item.status === 'uploading'"
                height="6"
                color="primary"
                :value="(item.progress || 0) * 100"
              />
            </v-list-item-content>
            <v-list-item-action class="d-flex align-center">
              <div v-if="item.status === 'uploading'">
                {{ formatUploadProgress(item.progress || 0) }}
              </div>
              <v-progress-circular
                v-else-if="item.status === 'pending'"
                indeterminate
                size="20"
                width="2"
                color="grey lighten-1"
              />
              <v-icon
                v-else
                color="green"
              >
                mdi-check-circle
              </v-icon>
            </v-list-item-action>
          </v-list-item>
        </v-list>
      </template>
      <div
        v-else
        class="cloud-status-empty"
      >
        No files in the queue.
      </div>
    </section>
  </v-container>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { CloudSyncDisplayItem } from './types'

export default Vue.extend({
  name: 'CloudSyncStatusTab',
  props: {
    summaryMessage: {
      type: String,
      required: true,
    },
    items: {
      type: Array as PropType<CloudSyncDisplayItem[]>,
      default: () => [],
    },
    activeCount: {
      type: Number,
      required: true,
    },
    pendingCount: {
      type: Number,
      required: true,
    },
    getFileName: {
      type: Function as PropType<(path: string) => string>,
      required: true,
    },
    formatFileSize: {
      type: Function as PropType<(value: number) => string>,
      required: true,
    },
    formatUploadProgress: {
      type: Function as PropType<(progress: number) => string>,
      required: true,
    },
    missionsUrl: {
      type: String,
      required: true,
    },
  },
})
</script>

<style scoped>
.cloud-status-section + .cloud-status-section {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 16px;
}
.cloud-status-empty {
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.7);
  padding: 12px 0;
}
</style>
