import axios from 'axios'
import {
  Action,
  getModule,
  Module,
  Mutation,
  VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import notifications from '@/store/notifications'
import { system_information_service } from '@/types/frontend_services'
import { KernelMessage } from '@/types/system-information/kernel'
import { Netstat } from '@/types/system-information/netstat'
import { Platform } from '@/types/system-information/platform'
import {
  CPU, Disk, Info, Memory, Network, Process, System, Temperature,
} from '@/types/system-information/system'
import { callPeriodically } from '@/utils/helper_functions'

export enum FetchType {
    KernelType = 'kernel_buffer',
    NetstatType = 'netstat',
    PlatformType = 'platform',
    SystemType = 'system',
    SystemCpuType = 'system/cpu',
    SystemDiskType = 'system/disk',
    SystemInfoType = 'system/info',
    SystemMemoryType = 'system/memory',
    SystemNetworkType = 'system/network',
    SystemProcessType = 'system/process',
    SystemTemperatureType = 'system/temperature',
    SystemUnixTimeSecondsType = 'system/unix_time_seconds',
}

@Module({
  dynamic: true,
  store,
  name: 'system',
})
class SystemInformationStore extends VuexModule {
  API_URL = '/system-information'

  kernel_message: KernelMessage[] = [];

  netstat: Netstat | null = null;

  platform: Platform | null = null;

  socket: WebSocket | null = null;

  system: System | null = null;

  @Mutation
  appendKernelMessage(kernel_message: KernelMessage): void {
    this.kernel_message.push(kernel_message)
  }

  @Mutation
  updateKernelMessage(kernel_message: KernelMessage[]): void {
    this.kernel_message = kernel_message
  }

  @Mutation
  updateNetstat(netstat: Netstat): void {
    this.netstat = netstat
  }

  @Mutation
  updatePlatform(platform: Platform): void {
    this.platform = platform
  }

  @Mutation
  updateSystem(system: System): void {
    this.system = system
  }

  @Mutation
  updateSystemCpu(cpu: [CPU]): void {
    if (this.system) {
      this.system.cpu = cpu
    }
  }

  @Mutation
  updateSystemDisk(disk: [Disk]): void {
    if (this.system) {
      this.system.disk = disk
    }
  }

  @Mutation
  updateSystemInfo(info: Info): void {
    if (this.system) {
      this.system.info = info
    }
  }

  @Mutation
  updateSystemMemory(memory: Memory): void {
    if (this.system) {
      this.system.memory = memory
    }
  }

  @Mutation
  updateSystemNetwork(network: [Network]): void {
    if (this.system) {
      this.system.network = network
    }
  }

  @Mutation
  updateSystemProcess(process: [Process]): void {
    if (this.system) {
      this.system.process = process
    }
  }

  @Mutation
  updateSystemTemperature(temperature: [Temperature]): void {
    if (this.system) {
      this.system.temperature = temperature
    }
  }

  @Mutation
  updateSystemUnixTimeSeconds(unix_time_seconds: number): void {
    if (this.system) {
      this.system.unix_time_seconds = unix_time_seconds
    }
  }

  @Action
  async fetchKernelMessage(): Promise<void> {
    await this.fetchSystemInformation(FetchType.KernelType)
  }

  @Action
  async fetchNetstat(): Promise<void> {
    await this.fetchSystemInformation(FetchType.NetstatType)
  }

  @Action
  async fetchPlatform(): Promise<void> {
    await this.fetchSystemInformation(FetchType.PlatformType)
  }

  @Action
  async fetchSystem(): Promise<void> {
    await this.fetchSystemInformation(FetchType.SystemType)
  }

  @Action
  async fetchSystemInformation(type: FetchType): Promise<void> {
    // Do not fetch system specific information if system is not populate yet
    // system type does not have optional fields, they need to be populate before fetching it
    switch (type) {
      case FetchType.SystemCpuType:
      case FetchType.SystemDiskType:
      case FetchType.SystemInfoType:
      case FetchType.SystemMemoryType:
      case FetchType.SystemNetworkType:
      case FetchType.SystemProcessType:
      case FetchType.SystemTemperatureType:
      case FetchType.SystemUnixTimeSecondsType:
        if (!this.system) {
          await this.fetchSystemInformation(FetchType.SystemType)
          return
        }
        break
      default:
        break
    }

    await axios({
      method: 'get',
      url: `${this.API_URL}/${type}`,
      timeout: 10000,
    })
      .then((response) => {
        switch (type) {
          case FetchType.KernelType:
            this.updateKernelMessage(response.data)
            break
          case FetchType.NetstatType:
            this.updateNetstat(response.data)
            break
          case FetchType.PlatformType:
            this.updatePlatform(response.data)
            break
          case FetchType.SystemType:
            this.updateSystem(response.data)
            break
          case FetchType.SystemCpuType:
            this.updateSystemCpu(response.data)
            break
          case FetchType.SystemDiskType:
            this.updateSystemDisk(response.data)
            break
          case FetchType.SystemInfoType:
            this.updateSystemInfo(response.data)
            break
          case FetchType.SystemMemoryType:
            this.updateSystemMemory(response.data)
            break
          case FetchType.SystemNetworkType:
            this.updateSystemNetwork(response.data)
            break
          case FetchType.SystemProcessType:
            this.updateSystemProcess(response.data)
            break
          case FetchType.SystemTemperatureType:
            this.updateSystemTemperature(response.data)
            break
          case FetchType.SystemUnixTimeSecondsType:
            this.updateSystemUnixTimeSeconds(response.data)
            break
          default:
            console.error(`Invalid fetch type: ${type}`)
            break
        }
      })
      .catch((error) => {
        const message = `Could not fetch system information '${type}': ${error.message}`
        notifications.pushError({ service: system_information_service, type: 'SYSTEM_FETCH_FAIL', message })
      })
  }
}

export { SystemInformationStore }

const system_information: SystemInformationStore = getModule(SystemInformationStore)

system_information.fetchSystem()
callPeriodically(system_information.fetchPlatform, 5000)

// It appears that the store is incompatible with websockets or callbacks.
// Right now the only way to have it working is to have the websocket definition outside the store
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
const websocketUrl = `${protocol}://${window.location.host}${system_information.API_URL}/ws/kernel_buffer?start=0`
const socket = new WebSocket(websocketUrl)
socket.onmessage = (message) => {
  system_information.appendKernelMessage(JSON.parse(message.data))
}

export default system_information
