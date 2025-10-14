import { 
    Action,
    getModule,
    Module,
    VuexModule,
} from "vuex-module-decorators"

import Notifier from "@/libs/notifier"
import store from "@/store"
import { pardal_service } from "@/types/frontend_services"
import { SpeedTestResult } from "@/types/pardal"
import back_axios from "@/utils/api"

const notifier = new Notifier(pardal_service)

@Module({
    dynamic: true,
    store,
    name: 'pardal',
  })

class PardalStore extends VuexModule {
  API_URL = '/network-test'

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

export { PardalStore }

const pardal: PardalStore = getModule(PardalStore)

export default pardal
