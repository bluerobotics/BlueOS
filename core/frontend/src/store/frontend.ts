import { AxiosResponse } from 'axios'
import { nanoid } from 'nanoid'
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

  frontend_id = (() => {
    const id = nanoid(9)
    console.log('[FrontendStore] Frontend is assigned with ID:', id)
    return id
  })()

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
