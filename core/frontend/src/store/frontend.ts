import { AxiosResponse } from 'axios'
import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'

@Module({
  dynamic: true,
  store,
  name: 'frontend',
})

class FrontendStore extends VuexModule {
  backend_status_url = '/status'

  backend_status_request = null as Promise<AxiosResponse> | null

  backend_offline = false

  @Mutation
  setBackendStatusRequest(check: Promise<AxiosResponse> | null): void {
    this.backend_status_request = check
  }

  @Mutation
  setBackendOffline(offline: boolean): void {
    this.backend_offline = offline
  }
}

export { FrontendStore }

const frontend: FrontendStore = getModule(FrontendStore)
export default frontend
