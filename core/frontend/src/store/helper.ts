import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import store from '@/store'
import { helper_service } from '@/types/frontend_services'
import { Service, SpeedTestResult } from '@/types/helper'
import back_axios, { backend_offline_error } from '@/utils/api'

const notifier = new Notifier(helper_service)

type CheckSiteStatus = {
  site: string;
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

  has_internet = false

  services: Service[] = []

  checkInternetAccessTask = new OneMoreTime(
    { delay: 20000 },
  )

  updateWebServicesTask = new OneMoreTime(
    { delay: 5000 },
  )

  @Mutation
  setHasInternet(has_internet: boolean): void {
    this.has_internet = has_internet
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
        const has_internet = !Object.values(response.data as SiteStatus)
          .filter((item) => item.online)
          .isEmpty()

        this.setHasInternet(has_internet)
      })
      .catch((error) => {
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
        if (error === backend_offline_error) { throw new Error(error) }
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
}

export { PingStore }

const ping: PingStore = getModule(PingStore)

ping.checkInternetAccessTask.setAction(ping.checkInternetAccess)
ping.updateWebServicesTask.setAction(ping.updateWebServices)

export default ping
