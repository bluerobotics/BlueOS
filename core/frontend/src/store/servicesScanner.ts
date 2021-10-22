import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { Service } from '@/types/helper'

@Module({
  dynamic: true,
  store,
  name: 'services_scanner',
})

class ServicesScannerStore extends VuexModule {
  services: Service[] = []

  @Mutation
  updateFoundServices(services: Service[]): void {
    this.services = services
  }
}

export { ServicesScannerStore }

const services_scanner: ServicesScannerStore = getModule(ServicesScannerStore)
export default services_scanner
