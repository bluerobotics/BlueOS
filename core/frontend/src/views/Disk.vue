<template>
  <v-card height="100%">
    <v-tabs
      v-model="activeTab"
      centered
      icons-and-text
      show-arrows
    >
      <v-tabs-slider />
      <v-tab>
        Disk Usage
        <v-icon>mdi-harddisk</v-icon>
      </v-tab>
      <v-tab>
        Speed Test
        <v-icon>mdi-speedometer</v-icon>
      </v-tab>
    </v-tabs>
    <v-tabs-items v-model="activeTab">
      <!-- Disk Usage Tab -->
      <v-tab-item>
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
                <v-card-title class="py-2 d-flex align-center">
                  <span>{{ path }} {{ totalSize ? ` (${totalSize})` : '' }}</span>
                  <v-spacer />
                  <v-btn
                    icon
                    small
                    :disabled="!canGoUp"
                    @click="goUp"
                  >
                    <v-icon>mdi-arrow-up</v-icon>
                  </v-btn>
                  <v-spacer />
                  <v-btn
                    icon
                    small
                    color="red"
                    :disabled="selectedPaths.length === 0 || deleting"
                    :loading="deleting"
                    @click="confirmDeleteSelected"
                  >
                    <v-icon>mdi-delete</v-icon>
                  </v-btn>
                </v-card-title>
                <v-divider />
                <v-card-text class="pa-0">
                  <v-simple-table dense>
                    <thead>
                      <tr>
                        <th class="text-center select-col">
                          <v-checkbox
                            :input-value="allSelected"
                            :indeterminate="someSelected && !allSelected"
                            hide-details
                            dense
                            @click.stop="toggleSelectAll"
                          />
                        </th>
                        <th class="text-left">
                          Name
                        </th>
                        <th class="text-center usage-col">
                          Usage
                        </th>
                        <th class="text-right">
                          Size
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-if="!usage || usage.root.children.length === 0">
                        <td colspan="4" class="text-center grey--text text--darken-1">
                          No entries.
                        </td>
                      </tr>
                      <tr
                        v-for="child in sortedChildren"
                        :key="child.path"
                        :class="{ 'clickable-row': child.is_dir }"
                        @click="navigate(child)"
                      >
                        <td class="text-center select-col" @click.stop>
                          <v-checkbox
                            :input-value="isSelected(child.path)"
                            hide-details
                            dense
                            @click.stop="toggleSelection(child.path)"
                          />
                        </td>
                        <td>
                          <v-icon
                            left
                            small
                            :color="child.is_dir ? 'green darken-2' : 'amber darken-2'"
                          >
                            {{ child.is_dir ? 'mdi-folder' : 'mdi-file' }}
                          </v-icon>
                          {{ child.name }}
                        </td>
                        <td class="usage-col">
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
                      </tr>
                    </tbody>
                  </v-simple-table>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-container>
      </v-tab-item>

      <!-- Speed Test Tab -->
      <v-tab-item>
        <v-container class="d-flex flex-row align-center justify-center fluid">
          <v-card min-width="390px" class="ma-5">
            <v-card-title class="justify-center">
              Disk Speed Test
            </v-card-title>

            <v-divider />

            <v-col>
              <v-col class="d-flex justify-center">
                <v-progress-circular
                  v-if="speedTesting"
                  :rotate="90"
                  :width="15"
                  :indeterminate="speedTesting"
                  ratio="1"
                  color="primary"
                  size="200"
                >
                  <span v-if="speedTesting">Testing...</span>
                  <span v-else>Click to start</span>
                </v-progress-circular>

                <v-list v-else>
                  <v-list-item>
                    <v-list-item-icon>
                      <v-icon v-tooltip="'Write speed'">
                        mdi-alpha-w-box-outline
                      </v-icon>
                    </v-list-item-icon>
                    <v-list-item-subtitle>
                      {{ speedResult?.write_speed_mbps ? speedResult.write_speed_mbps.toFixed(2) : '...' }} MiB/s
                    </v-list-item-subtitle>
                  </v-list-item>

                  <v-list-item>
                    <v-list-item-icon>
                      <v-icon v-tooltip="'Read speed'">
                        mdi-alpha-r-box-outline
                      </v-icon>
                    </v-list-item-icon>
                    <v-list-item-subtitle>
                      {{ speedResult?.read_speed_mbps ? speedResult.read_speed_mbps.toFixed(2) : '...' }} MiB/s
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-col>

              <v-alert v-if="speedError" type="error" dense outlined class="ma-4">
                {{ speedError }}
              </v-alert>

              <v-alert
                v-if="speedResult && !speedResult.success"
                type="warning"
                dense
                outlined
                class="ma-4"
              >
                Test failed: {{ speedResult.error }}
              </v-alert>

              <div
                class="transition-swing pa-6"
                align="center"
                v-text="state"
              />

              <v-card-actions class="justify-center">
                <v-btn
                  color="primary"
                  :disabled="speedTesting"
                  @click="runSpeedTest"
                >
                  <v-icon>
                    mdi-play
                  </v-icon>
                </v-btn>
              </v-card-actions>
            </v-col>
          </v-card>
        </v-container>
      </v-tab-item>
    </v-tabs-items>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import disk_store from '@/store/disk'
import { DiskNode, DiskSpeedResult } from '@/types/disk'
import { prettifySize } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'DiskView',
  data() {
    return {
      activeTab: 0,
      path: '/',
      depth: 2,
      includeFiles: true,
      minSizeKb: 0,
      selectedPaths: [] as string[],
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
    speedResult(): DiskSpeedResult | null {
      return disk_store.speedResult
    },
    speedTesting(): boolean {
      return disk_store.speedTesting
    },
    speedError(): string | null {
      return disk_store.speedError
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
    allSelected(): boolean {
      const children = this.sortedChildren
      return children.length > 0 && children.every((child) => this.selectedPaths.includes(child.path))
    },
    someSelected(): boolean {
      const children = this.sortedChildren
      return children.some((child) => this.selectedPaths.includes(child.path))
    },
    state(): string {
      if (this.speedTesting) {
        return 'Running test...'
      }
      if (this.speedResult?.success) {
        return 'Test complete'
      }
      if (this.speedResult && !this.speedResult.success) {
        return 'Test failed'
      }
      return 'Click to start'
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
      this.clearSelection()
      this.path = parent
      this.fetchUsage()
    },
    navigate(node: DiskNode): void {
      if (!node.is_dir) {
        return
      }
      this.clearSelection()
      this.path = node.path
      this.fetchUsage()
    },
    async confirmDeleteSelected(): Promise<void> {
      if (this.selectedPaths.length === 0) {
        return
      }
      const confirmed = window.confirm(
        `Delete the following paths?\n${this.selectedPaths.join('\n')}\nThis cannot be undone.`,
      )
      if (!confirmed) {
        return
      }
      const targets = [...this.selectedPaths]
      const { succeeded } = await disk_store.deletePaths(targets)

      if (succeeded.length > 0) {
        this.selectedPaths = this.selectedPaths.filter((p) => !succeeded.includes(p))
        await this.fetchUsage()
      }
    },
    toggleSelection(path: string): void {
      if (this.selectedPaths.includes(path)) {
        this.selectedPaths = this.selectedPaths.filter((p) => p !== path)
      } else {
        this.selectedPaths = [...this.selectedPaths, path]
      }
    },
    isSelected(path: string): boolean {
      return this.selectedPaths.includes(path)
    },
    toggleSelectAll(): void {
      const children = this.sortedChildren.map((child) => child.path)
      if (this.allSelected) {
        this.selectedPaths = []
      } else {
        this.selectedPaths = [...children]
      }
    },
    clearSelection(): void {
      this.selectedPaths = []
    },
    getPercentage(sizeBytes: number): number {
      const parentSize = this.usage?.root?.size_bytes ?? 0
      if (parentSize <= 0) {
        return 0
      }
      return sizeBytes / parentSize * 100
    },
    async runSpeedTest(): Promise<void> {
      await disk_store.runSpeedTest(1024 * 1024 * 1024)
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
.select-col {
  width: 60px;
}
.usage-col {
  width: 220px;
  min-width: 220px;
}
</style>
