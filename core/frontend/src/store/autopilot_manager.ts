import { Module, Mutation, VuexModule } from 'vuex-module-decorators'

import store from '@/store'
import { AutopilotEndpoint } from '@/types/autopilot'

@Module({
  dynamic: true,
  store,
  name: 'autopilot_manager_store',
})

export default class AutopilotManagerStore extends VuexModule {
  API_URL = '/ardupilot-manager/v1.0'

  available_endpoints: AutopilotEndpoint[] = []

  updating_endpoints = true

  @Mutation
  setUpdatingEndpoints(updating: boolean): void {
    this.updating_endpoints = updating
  }

  @Mutation
  setAvailableEndpoints(available_endpoints: AutopilotEndpoint[]): void {
    this.available_endpoints = available_endpoints
    this.updating_endpoints = false
  }
}
