<template>
  <v-data-table
    dense
    :headers="filteredHeader"
    :items="process"
    class="pa-6"
    item-key="pid"
    :items-per-page="-1"
    :sort-by="['cpu_usage']"
    :sort-desc="[true]"
    :search="search"
    :custom-filter="filterName"
    :loading="!process"
    loading-text="Loading... Please wait"
  >
    <template #top>
      <v-text-field
        v-model="search"
        clearable
        label="Search"
        class="mx-4"
        prepend-inner-icon="mdi-magnify"
      />
      <v-row
        dense
        flat
        class="d-flex flex-wrap"
      >
        <v-checkbox
          v-for="header in headers"
          :key="header.text"
          v-model="filterHeader"
          :value="header.value"
          class="shrink mr-5"
          :label="header.text"
        />
      </v-row>
    </template>

    <template #item.cpu_usage="{ item }">
      <v-chip
        style="height: 25px"
        :color="getCpuColor(item.cpu_usage)"
        dark
      >
        {{ item.cpu_usage.toFixed(1) }}
      </v-chip>
    </template>
    <template #item.command="{ item }">
      {{ item.command.join(' ') }}
    </template>
  </v-data-table>
</template>

<script lang="ts">
import Vue from 'vue'

import system_information, { FetchType } from '@/store/system-information'
import { Process } from '@/types/system-information/system'

export default Vue.extend({
  name: 'Processes',
  data() {
    return {
      timer: 0,
      search: null,
      filterHeader: [
        'pid',
        'name',
        'cpu_usage',
        'parent_process',
        'status',
        'working_directory',
        'command',
      ],
      headers: [
        { text: 'PID', align: 'start', value: 'pid' },
        { text: 'Name', value: 'name' },
        { text: 'CPU (%)', value: 'cpu_usage' },
        { text: 'Parent PID', value: 'parent_process' },
        { text: 'Status', value: 'status' },
        { text: 'Running time', value: 'running_time' },
        { text: 'Memory (kB)', value: 'used_memory_kB' },
        { text: 'Virt. Memory (kB)', value: 'virtual_memory_kB' },
        { text: 'Working directory', value: 'working_directory' },
        { text: 'Root directory', value: 'root_directory' },
        { text: 'Command', value: 'command' },
        { text: 'Environment', value: 'environment' },
        { text: 'Executable path', value: 'executable_path' },
      ],
    }
  },
  computed: {
    process(): Process[] | undefined {
      return system_information.system?.process
    },
    filteredHeader(): Record<string, unknown>[] {
      return this.headers.filter((header) => this.filterHeader.includes(header.value))
    },
  },
  mounted() {
    this.timer = setInterval(() => system_information.fetchSystemInformation(FetchType.SystemProcessType), 5000)
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
  methods: {
    filterName(value: number | string | Array<string>, search: string, _item: unknown) {
      if (search == null || search === '') {
        return true
      }

      let our_value: number | string | Array<string> = value
      if (typeof our_value === 'number') {
        our_value = value.toString()
      }
      if (Array.isArray(value) && value.length && typeof value[0] === 'string') {
        our_value = value.join(' ')
      }

      return our_value != null
          && typeof our_value === 'string'
          && our_value.toString().toLowerCase().indexOf(search.toLowerCase()) !== -1
    },
    getCpuColor(cpu: number): string {
      // TODO: Work on a common gradient color interface
      if (cpu < 15) {
        return 'success'
      }
      if (cpu < 40) {
        return 'warning'
      }
      if (cpu < 60) {
        return 'orange'
      }
      if (cpu < 100) {
        return 'error'
      }
      return 'critical'
    },
  },
})
</script>
