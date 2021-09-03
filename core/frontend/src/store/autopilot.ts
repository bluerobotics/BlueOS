import { Module, VuexModule } from 'vuex-module-decorators'

import store from '@/store'

@Module({
  dynamic: true,
  store,
  name: 'autopilot_store',
})

export default class WifiStore extends VuexModule {
  API_URL = '/ardupilot-manager/v1.0'
}
