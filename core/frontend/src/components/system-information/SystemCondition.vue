<template>
  <v-row class="ma-5 d-flex justify-center">
    <system-condition-card
      v-for="(item, i) in [cpu, memory, disk, temperature]"
      :key="i"
      class="mx-auto my-6"
      :title="item.name"
      :icon="item.icon"
      :value="item.value"
      :text="item.text"
      :time="item.time"
    />
  </v-row>
</template>

<script lang="ts">
import Vue from 'vue'

import SystemConditionCard from '@/components/system-information/SystemConditionCard.vue'
import system_information, { FetchType } from '@/store/system-information'
import { Disk } from '@/types/system-information/system'
import { prettifySize } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'SystemCondition',
  components: {
    SystemConditionCard,
  },
  data() {
    return {
      timer: 0,
    }
  },
  // TODO: move to computeds
  computed: {
    cpu(): Record<string, unknown> {
      const cpus = system_information.system?.cpu

      const cpu_usage = cpus
        ? cpus.map((cpu) => cpu.usage).reduce((sum, value) => sum + value, 0) / cpus.length : 0

      const cpu_text = cpus
        ? cpus?.map((cpu) => `${cpu.name}: ${cpu.usage.toFixed(0)}% (${cpu.frequency}MHz)`).join('<br/>') : 'Loading..'

      const cpu_brand = cpus?.first()?.brand ?? 'None'

      return {
        name: `CPU ${cpu_brand}`,
        icon: 'mdi-memory',
        value: `${cpu_usage.toFixed(1)}%`,
        text: cpu_text,
        time: '1 minute ago',
      }
    },
    memory(): Record<string, unknown> {
      const memory = system_information.system?.memory

      const used_ram_memory = memory?.ram?.used_kB ?? 0
      const total_ram_memory = memory?.ram?.total_kB ?? 0
      const used_swap_memory = memory?.swap?.used_kB ?? 0
      const total_swap_memory = memory?.swap?.total_kB ?? 0

      const memory_text = `RAM: ${prettifySize(used_ram_memory)}/${prettifySize(total_ram_memory)}`
        + `<br/>SWAP: ${prettifySize(used_swap_memory)}/${prettifySize(total_swap_memory)}`

      return {
        name: 'Memory',
        icon: 'mdi-note-text',
        // eslint-disable-next-line
          value: `${((100 * used_ram_memory) / total_ram_memory).toFixed(1)}%`,
        text: memory_text,
        time: '1 minute ago',
      }
    },
    disk(): Record<string, unknown> {
      const disks = system_information.system?.disk
      const main_disk = disks?.find((disk) => disk.mount_point === '/')

      function get_space_disk(disk: Disk | undefined) : [number, number] {
        const free_disk_space = disk ? disk.available_space_B / 2 ** 30 : 0
        const total_disk_space = disk ? disk.total_space_B / 2 ** 30 : 0
        const used_disk_space = total_disk_space - free_disk_space
        return [used_disk_space, total_disk_space]
      }

      const [used_disk_space, total_disk_space] = get_space_disk(main_disk)

      const disk_text = disks
        ? disks
          ?.filter((disk) => disk.name !== '/dev/root') // Filter out docker binds
          ?.map(
            (disk): string => {
              const [used_disk_space_local, total_disk_space_local] = get_space_disk(disk)
              return `${disk.name} '${disk.mount_point}'<br/>`
            + `&emsp;&emsp;${used_disk_space_local.toFixed(3)}GB/${total_disk_space_local.toFixed(0)}GB`
            + ` (${disk.filesystem_type})`
            },
          ).join('<br/>') : 'Loading..'

      return {
        name: 'Disk',
        icon: 'mdi-sd',
        // eslint-disable-next-line
          value: `${((100 * used_disk_space) / total_disk_space).toFixed(1)}%`,
        text: disk_text,
        time: '1 minute ago',
      }
    },
    temperature(): Record<string, unknown> {
      const temperature_sensors = system_information.system?.temperature
      const main_sensor = temperature_sensors?.find((sensor) => sensor.name.toLowerCase().includes('cpu'))
      const main_temperature = main_sensor?.temperature.toFixed(1) ?? 'Loading..'
      console.log(`main_temperature: ${main_temperature}`)
      const temperature_text = temperature_sensors?.map(
        (sensor) => {
          const critical_temp = sensor.critical_temperature || 0
          return `${sensor.name} ${sensor.temperature.toFixed(1)}ºC`
        + `, Max: ${sensor.maximum_temperature.toFixed(1)}ºC, Crit: ${critical_temp.toFixed(1)}ºC`
        },
      ).join('<br/>') ?? 'Loading..'

      return {
        name: 'Temperature',
        icon: 'mdi-thermometer',
        value: `${main_temperature}ºC`,
        text: temperature_text,
        time: '1 minute ago',
      }
    },
  },
  mounted() {
    this.timer = setInterval(() => {
      system_information.fetchSystemInformation(FetchType.SystemCpuType)
      system_information.fetchSystemInformation(FetchType.SystemDiskType)
      system_information.fetchSystemInformation(FetchType.SystemMemoryType)
      system_information.fetchSystemInformation(FetchType.SystemTemperatureType)
    }, 2000)
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
})
</script>
