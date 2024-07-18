<template>
  <v-card class="main-card d-flex flex-column">
    <div
      v-if="loading"
      class="card-loading-overlay"
    >
      <SpinningLogo
        size="150"
      />
    </div>
    <v-icon
      v-if="extension.enabled && !container && !loading"
      v-tooltip="'This extension is enabled but the container is not running.'"
      class="container-not-up-alert"
      color="warning"
      size="35"
    >
      mdi-robot-dead
    </v-icon>
    <v-card-title class="pb-1 d-flex justify-space-between align-center">
      <div class="d-flex align-center">
        <v-avatar
          v-if="extensionData && extensionData.extension_logo"
          size="60"
          class="mr-3"
          rounded="0"
        >
          <v-img
            :src="extensionData.extension_logo"
            :alt="extension.name"
          />
        </v-avatar>
        <div>
          <div>{{ extension.name }}</div>
          <span
            class="d-block"
            style="color: grey;"
          >
            {{ extension.tag }}
          </span>
        </div>
      </div>
      <v-btn
        v-if="update_available"
        class="card-update-button"
        color="primary"
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
    <div
      style="flex-grow: 1;"
    />
    <v-card-actions class="card-actions">
      <v-btn
        v-if="extension.identifier !== 'blueos.major_tom'"
        :style="{ backgroundColor: buttonBgColor }"
        @click="$emit('uninstall', extension)"
      >
        Uninstall
      </v-btn>
      <v-btn
        :style="{ backgroundColor: buttonBgColor }"
        @click="$emit('showlogs', extension)"
      >
        View Logs
      </v-btn>
      <v-btn
        v-if="settings.is_pirate_mode"
        :style="{ backgroundColor: buttonBgColor }"
        @click="$emit('edit', extension)"
      >
        Edit
      </v-btn>
      <v-btn
        v-if="extension.enabled && container"
        :style="{ backgroundColor: buttonBgColor }"
        @click="$emit('disable', extension)"
      >
        Disable
      </v-btn>
      <v-btn
        v-if="!extension.enabled"
        :style="{ backgroundColor: buttonBgColor }"
        @click="$emit('enable', extension)"
      >
        Enable and start
      </v-btn>

      <v-btn
        v-if="extension.enabled && container"
        :style="{ backgroundColor: buttonBgColor }"
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

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import settings from '@/libs/settings'
import system_information from '@/store/system-information'
import { ExtensionData, InstalledExtensionData } from '@/types/kraken'
import { Disk } from '@/types/system-information/system'
import { prettifySize } from '@/utils/helper_functions'

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
    buttonBgColor() {
      return settings.is_dark_theme ? '#20455e' : '#BDE0F0'
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

      if (semver.compare(this.extension.tag, latest) >= 0) {
        return false
      }

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
.main-card {
  width: auto;
}

.card-actions {
  flex-wrap: wrap;
  justify-content: center;
  row-gap: 7px;
  margin-bottom: 10px;
}

.progress {
  border-radius: 3px;
  min-width: 150px;
  max-width: 300px;
}

.card-update-button {
  width: 200px;
  font-size: 0.8rem;
}

@media (max-width: 994px) {
  .main-card {
    width: 600px;
    min-width: 400px;
  }
}

@media (max-width: 545px) {
  .card-update-button {
    margin-top: 5px;
    width: 100%;
  }
}

.card-loading-overlay {
  position: absolute;
  display: flex;
  justify-content: center;
  align-items: center;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  backdrop-filter: blur(3px);
  z-index: 9999 !important;
}

.container-not-up-alert {
  position: absolute;
  right: 13px;
  top: 13px;
}
</style>
