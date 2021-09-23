import { Module, Mutation, VuexModule } from 'vuex-module-decorators'

import store from '@/store'
import { AutopilotEndpoint, Platform } from '@/types/autopilot'

@Module({
  dynamic: true,
  store,
  name: 'autopilot_manager_store',
})

export default class AutopilotManagerStore extends VuexModule {
  API_URL = '/ardupilot-manager/v1.0'

  available_endpoints: AutopilotEndpoint[] = []

  current_platform: Platform = Platform.Undefined

  updating_endpoints = true

  @Mutation
  setUpdatingEndpoints(updating: boolean): void {
    this.updating_endpoints = updating
  }

  @Mutation
  setCurrentPlatform(platform: Platform): void {
    this.current_platform = platform
  }

  @Mutation
  setAvailableEndpoints(available_endpoints: AutopilotEndpoint[]): void {
    this.available_endpoints = available_endpoints
    this.updating_endpoints = false
  }
}
