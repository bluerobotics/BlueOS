import { Module, Mutation, VuexModule } from 'vuex-module-decorators'
import { Service } from '@/types/SERVICE'
import store from '@/store'

@Module({
  dynamic: true,
  store,
  name: 'servicesScanner',
})

export default class ServicesScannerStore extends VuexModule {
  services: Service[] = []


  @Mutation
  updateFoundServices (services: Service[]): void {
    this.services = services
  }
}
