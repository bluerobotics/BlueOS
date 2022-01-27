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
import { System } from '@/types/system-information/system'

enum FetchType {
    KernelType = 'kernel_buffer',
    NetstatType = 'netstat',
    PlatformType = 'platform',
    SystemType = 'system',
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

  system: System | null = null;

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
    console.debug('System update!')
    this.system = system
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
    console.debug('System!')
    await this.fetchSystemInformation(FetchType.SystemType)
  }

  @Action
  async fetchSystemInformation(type: FetchType): Promise<void> {
    await axios({
      method: 'get',
      url: `${this.API_URL}/${type}`,
      timeout: 10000,
    })
      .then((response) => {
        console.debug(`RESPONSE: ${type}`)
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
            console.debug('system case')
            this.updateSystem(response.data)
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
export default system_information
