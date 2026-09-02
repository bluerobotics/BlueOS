import {
  Action,
  getModule,
  Mutation,
  VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import store from '@/store'
import { system_information_service } from '@/types/frontend_services'
import { KernelMessage } from '@/types/system-information/kernel'
import { JournalEntry, JournalResponse } from '@/types/system-information/journal'
import { Model } from '@/types/system-information/model'
import { Netstat } from '@/types/system-information/netstat'
import { Platform } from '@/types/system-information/platform'
import { Serial } from '@/types/system-information/serial'
import {
  CPU, Disk, Info, Memory, Network, Process, System, Temperature,
} from '@/types/system-information/system'
import back_axios, { isBackendOffline } from '@/utils/api'
import { linux2restProbeRateBps } from '@/utils/linux2rest'
import { DynamicModule as Module } from '@/utils/vuex'

export enum FetchType {
    ModelType = 'model',
    NetstatType = 'netstat',
    PlatformType = 'platform',
    SerialType = 'serial?udev=true',
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

const notifier = new Notifier(system_information_service)

const system_information_subscribers: Partial<Record<FetchType, number>> = {
  [FetchType.SystemCpuType]: 0,
  [FetchType.SystemMemoryType]: 0,
  [FetchType.SystemDiskType]: 0,
  [FetchType.SystemTemperatureType]: 0,
  [FetchType.SystemNetworkType]: 0,
  [FetchType.PlatformType]: 0,
}

function subscribedSystemFetchTypes(): FetchType[] {
  return (Object.keys(system_information_subscribers) as FetchType[])
    .filter((type) => type !== FetchType.PlatformType && (system_information_subscribers[type] ?? 0) > 0)
}

function hasSystemSubscribers(): boolean {
  return subscribedSystemFetchTypes().length > 0
}

/** Return a new name list only when the set of interface names changed (keeps App tray stable). */
function nextNetworkInterfaceNames(previous: string[], networks: Network[] | undefined): string[] | undefined {
  const names = networks?.map(({ name }) => name) ?? []
  const same_set = previous.length === names.length
    && previous.every((name) => names.includes(name))
    && names.every((name) => previous.includes(name))
  return same_set ? undefined : names
}

function resumeOrStart(task: OneMoreTime): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const state = task as any
  if (state.isPaused) {
    task.resume()
  } else if (!state.isRunning && !state.timeoutId) {
    task.start()
  }
}

@Module({
  dynamic: true,
  store,
  name: 'system',
})
class SystemInformationStore extends VuexModule {
  API_URL = '/system-information'

  kernel_message: KernelMessage[] = []

  journal_entries: JournalEntry[] = []

  model: Model | null = null

  netstat: Netstat | null = null

  platform: Platform | null = null

  socket: WebSocket | null = null

  system: System | null = null

  serial: Serial | null = null

  // Stable interface name list for App tray widgets — updated only when the set of names changes.
  network_interface_names: string[] = []

  fetchPlatformTask = new OneMoreTime(
    { delay: 5000, autostart: false },
  )

  fetchSubscribedSystemInformationTask = new OneMoreTime(
    { delay: 2000, autostart: false },
  )

  @Mutation
  appendKernelMessage(kernel_message: [KernelMessage]): void {
    this.kernel_message = this.kernel_message.concat(kernel_message)
  }

  @Mutation
  appendJournalEntries(response: JournalResponse): void {
    this.journal_entries = this.journal_entries.concat(response.entries)
  }

  @Mutation
  clearKernelMessages(): void {
    this.kernel_message = []
  }

  @Mutation
  clearJournalEntries(): void {
    this.journal_entries = []
  }

  @Mutation
  updateModel(model: Model): void {
    this.model = model
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
  updateSerial(serial: Serial): void {
    this.serial = serial
  }

  @Mutation
  updateSystem(system: System): void {
    this.system = system
    const names = nextNetworkInterfaceNames(this.network_interface_names, system.network)
    if (names) {
      this.network_interface_names = names
    }
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
      for (const currentDisk of disk) {
        const previousDisk = this.system.disk?.find(
          (d) => d.mount_point === currentDisk.mount_point,
        )

        // write_rate_Bps is frontend-only; linux2rest does not send it. Keep the last
        // computed rate while the capacity snapshot is unchanged (zero delta).
        if (currentDisk.write_rate_Bps === undefined) {
          currentDisk.write_rate_Bps = previousDisk?.write_rate_Bps ?? 0
        }

        if (previousDisk) {
          const currentUsed = currentDisk.total_space_B - currentDisk.available_space_B
          const previousUsed = previousDisk.total_space_B - previousDisk.available_space_B
          const disk_delta = currentUsed - previousUsed
          if (disk_delta !== 0) {
            // available_space_B only changes on linux2rest Sampler ticks (5s), not on
            // the 2s frontend poll. Dividing by poll dt inflates the rate by 5/2 and a
            // later zero delta freezes that value on screen.
            // Used-space can drop (deletes); clamp to 0 because this widget is a write rate.
            currentDisk.write_rate_Bps = linux2restProbeRateBps(disk_delta)
          }
        }
      }
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
  updateSystemNetwork(networks: [Network]): void {
    if (this.system) {
      // Use linux2rest/sysinfo per-sample deltas (received_B / transmitted_B), not a
      // frontend re-diff of total_*. Those deltas are already saturating and match the
      // Sampler window (LINUX2REST_SYSTEM_SAMPLE_INTERVAL_S).
      for (const network of networks) {
        network.download_speed = linux2restProbeRateBps(network.received_B)
        network.upload_speed = linux2restProbeRateBps(network.transmitted_B)
      }
      this.system.network = networks
      const names = nextNetworkInterfaceNames(this.network_interface_names, networks)
      if (names) {
        this.network_interface_names = names
      }
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
  async fetchModel(): Promise<void> {
    await this.fetchSystemInformation(FetchType.ModelType)
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
  async fetchSerial(): Promise<void> {
    await this.fetchSystemInformation(FetchType.SerialType)
  }

  @Action
  async fetchSystem(): Promise<void> {
    await this.fetchSystemInformation(FetchType.SystemType)
  }

  @Action
  async fetchSubscribedSystemInformation(): Promise<void> {
    const fetches = subscribedSystemFetchTypes().map((type) => this.fetchSystemInformation(type))
    if (fetches.length === 0) {
      return
    }
    await Promise.all(fetches)
  }

  @Action
  subscribeSystemInformation(types: FetchType[]): void {
    types.forEach((type) => {
      if (system_information_subscribers[type] === undefined) {
        return
      }
      system_information_subscribers[type]! += 1
    })

    if (hasSystemSubscribers()) {
      resumeOrStart(this.fetchSubscribedSystemInformationTask)
    }
    if ((system_information_subscribers[FetchType.PlatformType] ?? 0) > 0) {
      resumeOrStart(this.fetchPlatformTask)
    }
  }

  @Action
  unsubscribeSystemInformation(types: FetchType[]): void {
    types.forEach((type) => {
      if (system_information_subscribers[type] === undefined) {
        return
      }
      system_information_subscribers[type] = Math.max(0, system_information_subscribers[type]! - 1)
    })

    if (!hasSystemSubscribers()) {
      this.fetchSubscribedSystemInformationTask.stop()
    }
    if ((system_information_subscribers[FetchType.PlatformType] ?? 0) === 0) {
      this.fetchPlatformTask.stop()
    }
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

    await back_axios({
      method: 'get',
      url: `${this.API_URL}/${type}`,
      timeout: 10000,
    })
      .then((response) => {
        switch (type) {
          case FetchType.ModelType:
            this.updateModel(response.data)
            break
          case FetchType.NetstatType:
            this.updateNetstat(response.data)
            break
          case FetchType.PlatformType:
            this.updatePlatform(response.data)
            break
          case FetchType.SerialType:
            this.updateSerial(response.data)
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
            throw new Error(`Invalid fetch type: ${type}`)
            break
        }
      })
      .catch((error) => {
        if (isBackendOffline(error)) { return }
        const message = `Could not fetch system information '${type}': ${error.message}`
        notifier.pushError('SYSTEM_FETCH_FAIL', message)
      })
  }
}

export { SystemInformationStore }

const system_information: SystemInformationStore = getModule(SystemInformationStore)

system_information.fetchSystem()
system_information.fetchPlatformTask.setAction(system_information.fetchPlatform)
system_information.fetchSubscribedSystemInformationTask.setAction(system_information.fetchSubscribedSystemInformation)

// Vuex store modules are a poor fit for WebSocket callbacks; keep sockets outside the store and
// open them only while a UI consumer is mounted (Kernel / Journal tabs).
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'

let kernel_socket: WebSocket | null = null
let journal_socket: WebSocket | null = null
let kernel_subscribers = 0
let journal_subscribers = 0

function closeSocket(socket: WebSocket | null): void {
  if (!socket) {
    return
  }
  socket.onmessage = null
  socket.onerror = null
  socket.onclose = null
  if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
    socket.close()
  }
}

export function subscribeKernelMessages(): void {
  kernel_subscribers += 1
  if (kernel_socket) {
    return
  }
  const socket = new WebSocket(`${protocol}://${window.location.host}${system_information.API_URL}/ws/kernel_buffer`)
  socket.onmessage = (message) => {
    system_information.appendKernelMessage(JSON.parse(message.data))
  }
  kernel_socket = socket
}

export function unsubscribeKernelMessages(): void {
  kernel_subscribers = Math.max(0, kernel_subscribers - 1)
  if (kernel_subscribers > 0) {
    return
  }
  closeSocket(kernel_socket)
  kernel_socket = null
  system_information.clearKernelMessages()
}

export function subscribeJournalEntries(): void {
  journal_subscribers += 1
  if (journal_socket) {
    return
  }
  const socket = new WebSocket(`${protocol}://${window.location.host}${system_information.API_URL}/ws/journal`)
  socket.onmessage = (message) => {
    system_information.appendJournalEntries(JSON.parse(message.data))
  }
  journal_socket = socket
}

export function unsubscribeJournalEntries(): void {
  journal_subscribers = Math.max(0, journal_subscribers - 1)
  if (journal_subscribers > 0) {
    return
  }
  closeSocket(journal_socket)
  journal_socket = null
  system_information.clearJournalEntries()
}

export default system_information
