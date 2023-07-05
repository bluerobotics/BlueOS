import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import store from '@/store'
import { helper_service } from '@/types/frontend_services'
import { SpeedTestResult } from '@/types/helper'
import back_axios from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

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

  @Mutation
  setHasInternet(has_internet: boolean): void {
    this.has_internet = has_internet
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
}

export { PingStore }

const ping: PingStore = getModule(PingStore)
callPeriodically(ping.checkInternetAccess, 20000)
export default ping
