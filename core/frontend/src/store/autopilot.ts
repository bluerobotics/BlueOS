import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import { MavAutopilot, MavType } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import { Message as M2R } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-message'
import store from '@/store'
import Parameter from '@/types/autopilot/parameter'
// eslint-disable-next-line import/no-cycle
import ParameterFetcher from '@/types/autopilot/parameter-fetcher'


import {
  FRAME_CLASS as ROVER_FRAME_CLASS,
  FRAME_TYPE as ROVER_FRAME_TYPE,
} from '@/types/autopilot/parameter-rover-enums'

import {
  FRAME_CONFIG as SUB_FRAME_CONFIG,
} from '@/types/autopilot/parameter-sub-enums'

import autopilot_manager from './autopilot_manager'

import { vehicle_folder } from '@/components/vehiclesetup/viewers/modelHelper'

const models: Record<string, string> = import.meta.glob('/public/assets/vehicles/models/**', { eager: true })


const parameterFetcher = new ParameterFetcher()

@Module({
  dynamic: true,
  store,
  name: 'autopilot_data',
})

class AutopilotStore extends VuexModule {
  parameters: Parameter[] = []

  parameters_loaded = 0

  parameters_total = 0

  vehicle = 'unknown'

  finished_loading = false

  metadata_loaded = false

  reboot_required = false

  autopilot_type = MavAutopilot.MAV_AUTOPILOT_INVALID

  system_id = 1

  verhicle_armed = false

  last_heartbeat_date: Date = new Date()

  get parameter() {
    return (name: string): Parameter | undefined => this.parameters.find((parameter) => parameter.name === name)
  }

  get parameterRegex() {
    return (pattern: string): Parameter[] => {
      const tester = new RegExp(pattern)
      return this.parameters.filter((parameter) => tester.test(parameter.name))
    }
  }

  get parameterFilter() {
    return (user_filter: (param: Parameter) => boolean) => this.parameters.filter(
      (param: Parameter) => user_filter(param),
    )
  }

  get vehicle_type(): string {
    return autopilot_manager.vehicle_type
  }

  get frame_type(): number | undefined {
    const mav_type = 'MAV_TYPE_' + autopilot_manager.vehicle_type?.toUpperCase().replace(' ', '_')
    switch (mav_type) {
      case MavType.MAV_TYPE_SUBMARINE:
        return this.parameter('FRAME_CONFIG')?.value
      case MavType.MAV_TYPE_SURFACE_BOAT:
        return this.parameter('FRAME_CLASS')?.value
        // TODO: other vehicles
      default:
        return undefined
    }
  }

  get frame_name(): string | undefined {
    switch (this.vehicle_type) {
      case 'Submarine':
        return Object.entries(SUB_FRAME_CONFIG).find((key, value) => value === this.frame_type)?.[1] as string
      case 'Surface Boat':
        // we already know it is a boat, so check only TYPE and ignore CLASS (rover/boat/balancebot)
        return Object.entries(ROVER_FRAME_CLASS).find((key, value) => value === this.frame_type)?.[1] as string
     default:
        break
    }
    return undefined
  }


  get vehicle_model() {
    const frame = this.frame_type
    if (!this.vehicle_type || frame === undefined) {
      return ''
    }
    const release_path = `assets/vehicles/models/${vehicle_folder()}/${this.frame_name}.glb`
    if (models[`/public/${release_path}`]) {
      return `/assets/vehicles/models/${vehicle_folder()}/${this.frame_name}.glb`
    }
    return ''
  }

  get is_safe() {
    // We can potentially check for external things here
    return !this.verhicle_armed
  }

  @Mutation
  reset(): void {
    this.parameters = []
    parameterFetcher.reset()
    this.finished_loading = false
    this.metadata_loaded = false
    this.parameters_loaded = 0
    this.parameters_total = 0
  }

  @Mutation
  setParameters(parameters: Parameter[]): void {
    this.parameters = parameters
  }

  @Mutation
  setSystemId(id: number): void {
    this.system_id = id
  }

  @Mutation
  setAutopilotType(autopilot_type: MavAutopilot): void {
    this.autopilot_type = autopilot_type
  }

  @Mutation
  setMetadataLoaded(loaded: boolean): void {
    this.metadata_loaded = loaded
    this.finished_loading = this.parameters_loaded >= this.parameters_total && this.metadata_loaded
  }

  @Mutation
  setLoadedParametersCount(count: number): void {
    this.parameters_loaded = count
    this.finished_loading = this.parameters_loaded >= this.parameters_total && this.metadata_loaded
  }

  @Mutation
  setRebootRequired(required: boolean): void {
    this.reboot_required = required
  }

  @Mutation
  setTotalParametersCount(count: number): void {
    this.parameters_total = count
    this.finished_loading = this.parameters_loaded >= this.parameters_total && this.metadata_loaded
  }

  @Mutation
  setVehicleArmed(armed: boolean): void {
    this.verhicle_armed = armed
  }

  @Mutation
  setLastHeartbeatDate(date: Date): void {
    this.last_heartbeat_date = date
  }
}

export { AutopilotStore }

const autopilot_data: AutopilotStore = getModule(AutopilotStore)
parameterFetcher.setStore(autopilot_data)
export default autopilot_data
