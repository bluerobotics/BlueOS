<template>
  <v-container fluid>
    <v-row v-if="error">
      <v-col cols="12">
        <v-alert type="error" dense outlined>
          {{ error }}
        </v-alert>
      </v-col>
    </v-row>
    <v-row v-if="loading">
      <v-col cols="12">
        <v-progress-linear
          color="primary"
          indeterminate
          height="6"
          rounded
          class="mb-2"
        />
      </v-col>
    </v-row>
    <v-row v-else>
      <v-col cols="12">
        <v-card outlined>
          <v-card-title class="py-2 d-flex justify-space-between align-center">
            <span>{{ path }} {{ totalSize ? ` (${totalSize})` : '' }}</span>
            <v-btn
              icon
              small
              :disabled="!canGoUp"
              @click="goUp"
            >
              <v-icon>mdi-arrow-up</v-icon>
            </v-btn>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-0">
            <v-simple-table dense>
              <thead>
                <tr>
                  <th class="text-left">
                    Name
                  </th>
                  <th class="text-center" style="width: 150px;">
                    Usage
                  </th>
                  <th class="text-right">
                    Size
                  </th>
                  <th class="text-center">
                    Type
                  </th>
                  <th class="text-center">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!usage || usage.root.children.length === 0">
                  <td colspan="5" class="text-center grey--text text--darken-1">
                    No entries.
                  </td>
                </tr>
                <tr
                  v-for="child in sortedChildren"
                  :key="child.path"
                  :class="{ 'clickable-row': child.is_dir }"
                  @click="navigate(child)"
                >
                  <td>
                    <v-icon left small>
                      {{ child.is_dir ? 'mdi-folder' : 'mdi-file' }}
                    </v-icon>
                    {{ child.name }}
                  </td>
                  <td>
                    <v-progress-linear
                      :value="getPercentage(child.size_bytes)"
                      height="16"
                      rounded
                      color="primary"
                    >
                      <template #default>
                        <span class="text-caption white--text">
                          {{ getPercentage(child.size_bytes).toFixed(1) }}%
                        </span>
                      </template>
                    </v-progress-linear>
                  </td>
                  <td class="text-right">
                    {{ prettifySize(child.size_bytes / 1024) }}
                  </td>
                  <td class="text-center">
                    {{ child.is_dir ? 'Dir' : 'File' }}
                  </td>
                  <td class="text-center">
                    <v-btn
                      icon
                      small
                      color="red"
                      :loading="deleting"
                      @click.stop="confirmDelete(child)"
                    >
                      <v-icon small>
                        mdi-delete
                      </v-icon>
                    </v-btn>
                  </td>
                </tr>
              </tbody>
            </v-simple-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import disk_store from '@/store/disk'
import { DiskNode } from '@/types/disk'
import { prettifySize } from '@/utils/helper_functions'

export default Vue.extend({
  data() {
    return {
      path: '/',
      depth: 2,
      includeFiles: true,
      minSizeKb: 0,
    }
  },
  computed: {
    usage() {
      return disk_store.usage
    },
    loading(): boolean {
      return disk_store.loading
    },
    deleting(): boolean {
      return disk_store.deleting
    },
    error(): string | null {
      return disk_store.error
    },
    sortedChildren(): DiskNode[] {
      if (!this.usage) {
        return []
      }
      return [...this.usage.root.children].sort((a, b) => b.size_bytes - a.size_bytes)
    },
    canGoUp(): boolean {
      const currentPath = this.path as string
      return currentPath !== '/'
    },
    totalSize(): string {
      if (!this.usage?.root?.size_bytes) {
        return ''
      }
      return prettifySize(this.usage.root.size_bytes / 1024)
    },
  },
  mounted(): void {
    this.fetchUsage()
  },
  methods: {
    async fetchUsage(): Promise<void> {
      const currentPath = this.path as string
      const currentDepth = this.depth as number
      const currentIncludeFiles = this.includeFiles as boolean
      const currentMinSizeKb = this.minSizeKb as number
      await disk_store.fetchUsage({
        path: currentPath || '/',
        depth: Math.max(currentDepth, 0),
        include_files: currentIncludeFiles,
        min_size_bytes: Math.max(0, currentMinSizeKb * 1024),
      })
    },
    goUp(): void {
      if (!this.canGoUp) {
        return
      }
      const currentPath = this.path as string
      const trimmed = currentPath.endsWith('/') ? currentPath.slice(0, -1) : currentPath
      const parent = trimmed.substring(0, trimmed.lastIndexOf('/')) || '/'
      this.path = parent
      this.fetchUsage()
    },
    navigate(node: DiskNode): void {
      if (!node.is_dir) {
        return
      }
      this.path = node.path
      this.fetchUsage()
    },
    async confirmDelete(node: DiskNode): Promise<void> {
      const confirmed = window.confirm(`Delete ${node.path}? This cannot be undone.`)
      if (!confirmed) {
        return
      }
      await disk_store.deletePath(node.path)
    },
    getPercentage(sizeBytes: number): number {
      const parentSize = this.usage?.root?.size_bytes ?? 0
      if (parentSize <= 0) {
        return 0
      }
      return sizeBytes / parentSize * 100
    },
    prettifySize,
  },
})
</script>

<style scoped>
.clickable-row {
  cursor: pointer;
}
.clickable-row:hover {
  background-color: rgba(0, 0, 0, 0.05);
}
</style>
