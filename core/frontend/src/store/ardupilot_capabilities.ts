import {
  getModule,
Module, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import autopilot_data from "./autopilot"

@Module({
  dynamic: true,
  store,
  name: 'ardupilot_capabilities',
})

class ArdupilotCapabilitiesStore extends VuexModule {

  get firmware_supports_actuators(): boolean {
    return autopilot_data.parameter('ACTUATOR1_INC') !== undefined
  }
}

export { ArdupilotCapabilitiesStore }

const ardupilot_capabilities: ArdupilotCapabilitiesStore = getModule(ArdupilotCapabilitiesStore)
export default ardupilot_capabilities
