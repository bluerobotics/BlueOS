import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { DHCPServerDetails, EthernetInterface } from '@/types/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import Notifier from '@/libs/notifier'

const notifier = new Notifier(ethernet_service)

@Module({
  dynamic: true,
  store,
  name: 'ethernet',
})

class EthernetStore extends VuexModule {
  API_URL = '/cable-guy/v1.0'

  available_interfaces: EthernetInterface[] = []

  updating_interfaces = true

  @Mutation
  setUpdatingInterfaces(updating: boolean): void {
    this.updating_interfaces = updating
  }

  @Mutation
  setInterfaces(ethernet_interfaces: EthernetInterface[]): void {
    this.available_interfaces = ethernet_interfaces
    this.updating_interfaces = false
  }

  @Action
  async addAddress(payload: { interface_name: string, ip_address: string }): Promise<void> {
    this.context.commit('setUpdatingInterfaces', true)

    await back_axios({
      method: 'post',
      url: `${this.API_URL}/address`,
      timeout: 10000,
      params: {
        interface_name: payload.interface_name,
        ip_address: payload.ip_address,
      },
    })
      .catch((error) => {
        notifier.pushBackError('ETHERNET_ADDRESS_CREATION_FAIL', error)
        throw error
      })
  }

  @Action
  async deleteAddress(payload: { interface_name: string, ip_address: string }): Promise<void> {
    this.context.commit('setUpdatingInterfaces', true)

    await back_axios({
      method: 'delete',
      url: `${this.API_URL}/address`,
      timeout: 10000,
      params: {
        interface_name: payload.interface_name,
        ip_address: payload.ip_address,
      },
    })
      .catch((error) => {
        notifier.pushError('ETHERNET_ADDRESS_DELETE_FAIL', error)
        throw error
      })
  }

  @Action
  async addDHCPServer(payload: { interface_name: string, ipv4_gateway: string, is_backup_server: boolean }): Promise<void> {
    this.context.commit('setUpdatingInterfaces', true)

    await back_axios({
      method: 'post',
      url: `${this.API_URL}/dhcp`,
      timeout: 10000,
      params: {
        interface_name: payload.interface_name,
        ipv4_gateway: payload.ipv4_gateway,
        is_backup_server: payload.is_backup_server,
      },
    })
      .catch((error) => {
        notifier.pushBackError('DHCP_SERVER_ADD_FAIL', error)
        throw error
      })
      .finally(() => {
        this.context.commit('setUpdatingInterfaces', false)
      })
  }

  @Action
  async RemoveDHCPServer(interface_name: string): Promise<void> {
    await back_axios({
      method: 'delete',
      url: `${this.API_URL}/dhcp`,
      timeout: 10000,
      params: {
        interface_name: interface_name,
      },
    })
      .catch((error) => {
        const message = `Could not remove DHCP server from interface '${interface_name}': ${error.message}.`
        notifier.pushError('DHCP_SERVER_REMOVE_FAIL', message)
      })
  }

  @Action
  async getDHCPServerDetails(interface_name: string): Promise<DHCPServerDetails> {
    return await back_axios({
      method: 'get',
      url: `${this.API_URL}/dhcp/details/${interface_name}`,
      timeout: 15000,
    })
  }

  @Action
  async getHostDNS() {
    return await back_axios({
      method: 'get',
      url: `${this.API_URL}/host_dns`,
      timeout: 10000,
    })
      .catch((error) => {
        this.context.commit('setInterfaces', [])
        notifier.pushBackError('HOST_DNS_FETCH_FAIL', error)
        throw error
      })
  }

  @Action
  async updateHostDNS(payload: { host_nameservers: string[], is_locked: boolean }): Promise<void> {
    await back_axios({
      method: 'post',
      url: `${this.API_URL}/host_dns`,
      timeout: 15000,
      data: {
        nameservers: payload.host_nameservers,
        lock: payload.is_locked,
      },
    })
      .then(() => {
        notifier.pushSuccess(
          'APPLY_HOST_DNS_SUCCESS',
          'Host DNS nameservers updated successfully!',
          true,
        )
      })
      .catch((error) => {
        notifier.pushError('APPLY_HOST_DNS_FAIL', error)
        throw error
      })
  }

  @Action
  async getAvailableInterfaces() {
    return await back_axios({
      method: 'get',
      url: `${this.API_URL}/interfaces`,
      // Necessary since the system can hang with dhclient timeouts
      timeout: 10000,
    })
      .catch((error) => {
        this.context.commit('setInterfaces', [])
        notifier.pushBackError('AVAILABLE_INTERFACES_FETCH_FAIL', error)
        throw error
      })
  }

  @Action
  async getAvailableEthernetInterfaces() {
    return await back_axios({
      method: 'get',
      url: `${this.API_URL}/ethernet`,
      // Necessary since the system can hang with dhclient timeouts
      timeout: 10000,
    })
      .catch((error) => {
        this.context.commit('setInterfaces', [])
        notifier.pushBackError('ETHERNET_AVAILABLE_INTERFACES_FETCH_FAIL', error)
        throw error
      })
  }

  @Action
  async setInterfacesPriority(interfaces: { name: string, priority: number }[]): Promise<void> {
    await back_axios({
      method: 'post',
      url: `${this.API_URL}/set_interfaces_priority`,
      timeout: 10000,
      data: interfaces,
    })
      .catch((error) => {
        const message = `Could not set network interface priorities: ${interfaces}, error: ${error}`
        notifier.pushError('INCREASE_NETWORK_INTERFACE_METRIC_FAIL', message)
        throw error
      })
      .then(() => {
        notifier.pushSuccess(
          'INCREASE_NETWORK_INTERFACE_METRIC_SUCCESS',
          'Network interface priorities successfully updated!',
          true,
        )
      })
  }

  @Action
  async triggerDynamicIP(interface_name: string): Promise<void> {
    await back_axios({
      method: 'post',
      url: `${this.API_URL}/dynamic_ip`,
      timeout: 10000,
      params: {
        interface_name: interface_name,
      },
    })
      .catch((error) => {
        const message = `Could not trigger for dynamic IP address on '${interface_name}': ${error.message}.`
        notifier.pushError('DYNAMIC_IP_TRIGGER_FAIL', message)
      })
  }
}

export { EthernetStore }

const ethernet: EthernetStore = getModule(EthernetStore)
export default ethernet
