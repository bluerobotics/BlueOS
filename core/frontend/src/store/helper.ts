import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import store from '@/store'
import { helper_service } from '@/types/frontend_services'
import { InternetConnectionState, Service, SpeedTestResult } from '@/types/helper'
import back_axios, { isBackendOffline } from '@/utils/api'

const notifier = new Notifier(helper_service)

type site = {
  hostname: string;
  path: string;
  port: number;
}

type CheckSiteStatus = {
  site: site;
  online: boolean;
  error: string | null;
};

type SiteStatus = Record<string, CheckSiteStatus>

@Module({
  dynamic: true,
  store,
  name: 'helper',
})

class PingStore extends VuexModule {
  API_URL = '/helper/latest'

  has_internet: InternetConnectionState = InternetConnectionState.UNKNOWN

  services: Service[] = []

  reachable_hosts: string[] = []

  checkInternetAccessTask = new OneMoreTime(
    { delay: 20000 },
  )

  updateWebServicesTask = new OneMoreTime(
    { delay: 5000 },
  )

  @Mutation
  setHasInternet(has_internet: InternetConnectionState): void {
    this.has_internet = has_internet
  }

  @Mutation
  setReachableHosts(hosts: string[]): void {
    this.reachable_hosts = hosts
  }

  @Mutation
  updateFoundServices(services: Service[]): void {
    this.services = services
  }

  @Action
  async checkInternetAccess(): Promise<void> {
    back_axios({
      method: 'get',
      url: `${this.API_URL}/check_internet_access`,
      timeout: 10000,
    })
      .then((response) => {
        const sites = Object.values(response.data as SiteStatus)
        const online_sites = sites.filter((item) => item.online)
        this.setReachableHosts(online_sites.map((item) => item.site.hostname))

        // If no sites are reachable, we're offline
        if (online_sites.length === 0) {
          this.setHasInternet(InternetConnectionState.OFFLINE)
          return
        }

        // If all sites are reachable, we're fully online
        if (online_sites.length === sites.length) {
          this.setHasInternet(InternetConnectionState.ONLINE)
          return
        }

        // If some sites are reachable but not all, we have limited connectivity
        this.setHasInternet(InternetConnectionState.LIMITED)
      })
      .catch((error) => {
        // If we can't even reach the backend, we're in an unknown state
        this.setHasInternet(InternetConnectionState.UNKNOWN)
        this.setReachableHosts([])
        notifier.pushBackError('INTERNET_CHECK_FAIL', error)
      })
  }

  @Action
  async checkInternetBestServer(): Promise<SpeedTestResult | void> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/internet_best_server`,
      timeout: 15000,
    })
      .then((response) => response.data as SpeedTestResult)
      .catch((error) => {
        notifier.pushBackError('INTERNET_BEST_SERVER_FAIL', error)
      })
  }

  @Action
  async checkInternetDownloadSpeed(): Promise<SpeedTestResult | void> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/internet_download_speed`,
      timeout: 15000,
    })
      .then((response) => response.data as SpeedTestResult)
      .catch((error) => {
        notifier.pushBackError('INTERNET_DOWNLOAD_SPEED_FAIL', error)
      })
  }

  @Action
  async checkInternetUploadSpeed(): Promise<SpeedTestResult | void> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/internet_upload_speed`,
      timeout: 15000,
    })
      .then((response) => response.data as SpeedTestResult)
      .catch((error) => {
        notifier.pushBackError('INTERNET_UPLOAD_SPEED_FAIL', error)
      })
  }

  @Action
  async checkPreviousInternetTestResult(): Promise<SpeedTestResult | void> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/internet_test_previous_result`,
      timeout: 15000,
    })
      .then((response) => response.data as SpeedTestResult)
      .catch((error) => {
        notifier.pushBackError('INTERNET_RESULT_SPEED_FAIL', error)
      })
  }

  @Action
  async checkWebServices(): Promise<Service[]> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/web_services`,
      timeout: 10000,
    })
      .then((response) => response.data as Service[])
      .catch((error) => {
        if (isBackendOffline(error)) { throw new Error(error) }
        const message = `Error scanning for services: ${error}`
        notifier.pushError('SERVICE_SCAN_FAIL', message)
        throw new Error(error)
      })
  }

  @Action
  async updateWebServices(): Promise<void> {
    this.checkWebServices()
      .then((services: Service[]) => {
        this.updateFoundServices(services.sort(
          (first: Service, second: Service) => first.port - second.port,
        ))
      })
      .catch(() => {
        this.updateFoundServices([])
      })
  }

  @Action
  async ping(options: {host: string, iface?: string}): Promise<boolean | undefined> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/ping`,
      params: { host: options.host, interface_addr: options.iface },
      timeout: 15000,
    })
      .then((response) => response.data as boolean)
      .catch(() => undefined)
  }
}

export { PingStore }

const ping: PingStore = getModule(PingStore)

ping.checkInternetAccessTask.setAction(ping.checkInternetAccess)
ping.updateWebServicesTask.setAction(ping.updateWebServices)

export default ping
