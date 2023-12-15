<template>
  <v-card>
    <v-card-title class="pb-0">
      {{ extension.docker.split('/').pop() }} <span
        class="ml-3"
        style="color: grey;"
      > {{ extension.tag }}</span>
      <v-btn
        v-if="update_available"
        color="primary"
        class="ml-auto"
        @click="$emit('update', extension, update_available)"
      >
        Update to {{ update_available }}
      </v-btn>
    </v-card-title>
    <span class="mt-0 mb-4 ml-4 text--disabled">{{ extension.docker }}</span>
    <v-card-text>
      <v-simple-table>
        <template #default>
          <tbody>
            <tr>
              <td>Status</td>
              <td>{{ extension.enabled ? getStatus() : "Disabled" }}</td>
            </tr>
            <tr v-if="extension.enabled">
              <td>CPU usage</td>
              <td>
                <v-progress-linear
                  class="progress"
                  :value="getCpuUsage() / getCpuLimit() / 0.01"
                  color="br_blue"
                  height="25"
                >
                  <template #default>
                    <SpinningLogo
                      v-if="loading || extension.enabled && !container"
                      size="20px"
                    />
                    <strong v-else-if="!isNaN(getCpuUsage())">
                      {{ `${getCpuUsage().toFixed(1)}% / ${getCpuLimit()}%` }}
                      {{ `(${(getCpuLimit() * cpus * 0.01).toFixed(1)} cores) ` }}
                    </strong>
                    <strong v-else>
                      N/A
                    </strong>
                  </template>
                </v-progress-linear>
              </td>
            </tr>
            <tr v-if="extension.enabled">
              <td>Memory usage</td>
              <td>
                <v-progress-linear
                  class="progress"
                  :value="getMemoryUsage()"
                  color="br_blue"
                  height="25"
                >
                  <template #default>
                    <SpinningLogo
                      v-if="loading || extension.enabled && !container"
                      size="20px"
                    />
                    <strong v-else-if="getMemoryUsage()?.toFixed">
                      {{ prettifySize(getMemoryUsage() * getMemoryLimit() * 100) }} /
                      {{ prettifySize(getMemoryLimit() * total_memory * 0.01) }}
                    </strong>
                    <strong v-else>
                      N/A
                    </strong>
                  </template>
                </v-progress-linear>
              </td>
            </tr>
            <tr v-if="extension.enabled">
              <td>Disk usage</td>
              <td>
                <v-progress-linear
                  class="progress"
                  :value="getDiskUsage()"
                  color="br_blue"
                  height="25"
                >
                  <template #default>
                    <SpinningLogo
                      v-if="loading || extension.enabled && !container"
                      size="20px"
                    />
                    <strong v-else-if="getDiskUsage()?.toFixed">
                      {{ prettifySize(getDiskUsage() * main_disk_size * 0.01) }} /
                      {{ prettifySize(main_disk_size) }}
                    </strong>
                    <strong v-else>
                      N/A
                    </strong>
                  </template>
                </v-progress-linear>
              </td>
            </tr>
          </tbody>
        </template>
      </v-simple-table>
    </v-card-text>
    <v-expansion-panels
      v-if="settings.is_pirate_mode"
      flat
    >
      <v-expansion-panel>
        <v-expansion-panel-header>
          Settings
        </v-expansion-panel-header>
        <v-expansion-panel-content>
          <json-viewer
            :value="JSON.parse(extension.permissions ?? '{}')"
            :expand-depth="5"
          />
        </v-expansion-panel-content>
      </v-expansion-panel>
    </v-expansion-panels>

    <v-expansion-panels
      v-if="settings.is_pirate_mode && extension.user_permissions"
      flat
    >
      <v-expansion-panel>
        <v-expansion-panel-header>
          User Custom Settings
        </v-expansion-panel-header>
        <v-expansion-panel-content>
          <json-viewer
            :value="JSON.parse(extension.user_permissions ?? '{}')"
            :expand-depth="5"
          />
        </v-expansion-panel-content>
      </v-expansion-panel>
    </v-expansion-panels>

    <v-card-actions class="card-actions">
      <v-btn @click="$emit('uninstall', extension)">
        Uninstall
      </v-btn>
      <v-btn @click="$emit('showlogs', extension)">
        View Logs
      </v-btn>
      <v-btn
        v-if="settings.is_pirate_mode"
        @click="$emit('edit', extension)"
      >
        Edit
      </v-btn>
      <v-btn
        v-if="extension.enabled"
        @click="$emit('disable', extension)"
      >
        Disable
      </v-btn>
      <v-btn
        v-if="!extension.enabled"
        @click="$emit('enable', extension)"
      >
        Enable and start
      </v-btn>

      <v-btn
        v-if="extension.enabled"
        @click="$emit('restart', extension)"
      >
        Restart
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import semver from 'semver'
import stable from 'semver-stable'
import Vue, { PropType } from 'vue'

import settings from '@/libs/settings'
import system_information from '@/store/system-information'
import { ExtensionData, InstalledExtensionData } from '@/types/kraken'
import { Disk } from '@/types/system-information/system'
import { prettifySize } from '@/utils/helper_functions'

import SpinningLogo from '../common/SpinningLogo.vue'

export default Vue.extend({
  name: 'InstalledExtensionCard',
  components: { SpinningLogo },
  props: {
    extension: {
      type: Object as PropType<InstalledExtensionData>,
      required: true,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    metrics: {
      type: Object as PropType<{cpu: number, memory: string}>,
      required: true,
    },
    container: {
      type: Object as PropType<{status: string}>,
      required: false,
      default: undefined as {status: string} | undefined,
    },
    extensionData: {
      type: Object as PropType<ExtensionData>,
      required: false,
      default: undefined as ExtensionData | undefined,
    },
  },
  data() {
    return {
      settings,
    }
  },
  computed: {
    cpus(): number {
      return system_information.system?.cpu?.length ?? 4
    },
    total_memory(): number | undefined {
      // Total system memory in kB
      const total_kb = system_information.system?.memory?.ram?.total_kB
      return total_kb ?? undefined
    },
    main_disk(): undefined | Disk {
      const disks = system_information.system?.disk
      return disks?.find((sensor) => sensor.mount_point === '/')
    },
    main_disk_size(): number {
      const value = this.main_disk?.total_space_B ?? 0
      return value / 1024 // Move to kB
    },
    update_available() : false | string {
      if (!this.extensionData) {
        return false
      }
      if (!semver.valid(this.extension.tag)) {
        return false
      }
      const versions: string[] = Object.keys(this.extensionData?.versions ?? {})
      const current_version = new semver.SemVer(this.extension.tag)
      // if is stable (which implies major >= 1), show latest stable
      if (stable.is(this.extension.tag) && current_version.major > 0) {
        return stable.max(versions) === this.extension.tag ? false : stable.max(versions)
      }
      // show the latest version regardless of stability
      // eslint-disable-next-line no-extra-parens
      const latest = versions.reduce((a: string, b: string) => (semver.compare(a, b) > 0 ? a : b))
      return this.extension.tag === latest ? false : latest
    },
  },
  methods: {
    prettifySize(size_kb: number) {
      return prettifySize(size_kb)
    },
    getCpuUsage(): number {
      return this.metrics?.cpu
    },
    getMemoryUsage(): string {
      return this.metrics?.memory
    },
    getDiskUsage(): string {
      return this.metrics?.disk
    },
    getMemoryLimit(): number | undefined {
      // Memory limit as a percentage of total system RAM
      const permissions_str = this.extension.user_permissions
        ? this.extension.user_permissions : this.extension.permissions
      const permissions = JSON.parse(permissions_str)
      const memory = permissions.HostConfig?.Memory
      if (this.total_memory && memory) {
        const limit_kB = memory / 1024
        return limit_kB / this.total_memory / 0.01
      }
      return 100
    },
    getCpuLimit(): number {
      // returns cpu cap in percentage of total cpu power
      const permissions_str = this.extension.user_permissions
        ? this.extension.user_permissions : this.extension.permissions
      const permissions = JSON.parse(permissions_str)
      const period = permissions.HostConfig?.CpuPeriod
      const quota = permissions.HostConfig?.CpuQuota
      if (quota && period) {
        return quota / (period * this.cpus * 0.01)
      }
      return 100
    },
    getStatus(): string {
      return this.container?.status ?? 'N/A'
    },
  },
})
</script>
<style scoped>
.card-actions {
  flex-wrap: wrap;
}
.progress {
  border-radius: 3px;
  min-width: 150px;
}
</style>
