<template>
  <v-sheet
    shaped
    class="pa-6 d-flex flex-column align-center"
  >
    <v-icon
      size="100"
    >
      {{ avatar }}
    </v-icon>
    <v-list dense>
      <v-list-item
        v-for="(item, i) in info"
        :key="i"
        selectable
      >
        <v-list-item-content>
          <v-list-item-title v-text="item.title" />
          <v-list-item-subtitle v-text="item.value" />
        </v-list-item-content>
      </v-list-item>
    </v-list>
  </v-sheet>
</template>

<script lang="ts">
import Vue from 'vue'

import system_information, { FetchType } from '@/store/system-information'

export default Vue.extend({
  name: 'Processes',
  data() {
    return {
      timer_unix: 0,
      timer_model: 0,
    }
  },
  computed: {
    info(): Record<string, unknown>[] | undefined {
      const info = system_information.system?.info
      const unix_time_seconds = system_information.system?.unix_time_seconds
      if (!info || !unix_time_seconds) {
        return undefined
      }

      return [
        {
          title: 'OS Type', value: `${info.system_name} ${info.os_version}`,
        },
        {
          title: 'Kernel', value: `${info.kernel_version}`,
        },
        {
          title: 'Model',
          value: `${system_information.model?.model ?? 'Unknown Model'} `
            + `- ${system_information.model?.arch ?? 'Unknown Architecture'} `
            + `(${system_information.model?.cpu_name ?? 'Unknown CPU'})`,
        },
        {
          title: 'Hostname', value: `${info.host_name}`,
        },
        {
          title: 'Time', value: new Date(unix_time_seconds * 1000).toTimeString(),
        },
      ]
    },
    avatar(): string | undefined {
      const info = system_information.system?.info
      const map = [
        { os: 'debian', icon: 'mdi-debian' },
        { os: 'arch', icon: 'mdi-arch' },
        { os: 'ubuntu', icon: 'mdi-ubuntu' },
        { os: 'apple', icon: 'mdi-apple' },
        { os: 'windows', icon: 'mdi-microsoft-windows' },
        { os: '', icon: 'mdi-linux' },
      ]

      return info
        ? map.find((item) => info.system_name.toLowerCase().includes(item.os))?.icon
        : 'mdi-help-circle'
    },
  },
  mounted() {
    this.timer_unix = setInterval(() => {
      system_information.fetchSystemInformation(FetchType.SystemUnixTimeSecondsType)
    }, 1000)
    this.timer_model = setInterval(() => system_information.fetchSystemInformation(FetchType.ModelType), 1000)
  },
  beforeDestroy() {
    clearInterval(this.timer_unix)
    clearInterval(this.timer_model)
  },
})
</script>
