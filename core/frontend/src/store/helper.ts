import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import store from '@/store'
import { helper_service } from '@/types/frontend_services'
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
}

export { PingStore }

const ping: PingStore = getModule(PingStore)
callPeriodically(ping.checkInternetAccess, 20000)
export default ping
