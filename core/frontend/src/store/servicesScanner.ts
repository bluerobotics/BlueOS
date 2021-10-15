import { Module, Mutation, VuexModule } from 'vuex-module-decorators'

import store from '@/store'
import { Service } from '@/types/helper'

@Module({
  dynamic: true,
  store,
  name: 'servicesScanner',
})

export default class ServicesScannerStore extends VuexModule {
  services: Service[] = []

  @Mutation
  updateFoundServices(services: Service[]): void {
    this.services = services
  }
}
