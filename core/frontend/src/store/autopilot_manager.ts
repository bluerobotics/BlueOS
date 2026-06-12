import { lte as sem_ver_lte } from 'semver'
import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import {
  AutopilotEndpoint, FirmwareInfo, FirmwareVehicleType,
  FlightController, SerialEndpoint, SITLFrame,
} from '@/types/autopilot'
import { SERVO_FUNCTION as SUB_SERVO_FUNCTION } from '@/types/autopilot/parameter-sub-enums'

// ArduSub <= 4.5.5 used RCIN9/RCIN10 for lights control; newer versions handle lights natively
const LEGACY_SUB_LIGHTS_MAX_VERSION = '4.5.5'
const LEGACY_SUB_LIGHTS1 = 59 // RCIN9
const LEGACY_SUB_LIGHTS2 = 60 // RCIN10

@Module({
  dynamic: true,
  store,
  name: 'autopilot',
})

class AutopilotManagerStore extends VuexModule {
  API_URL = '/ardupilot-manager/v1.0'

  available_endpoints: AutopilotEndpoint[] = []

  available_boards: FlightController[] = []

  current_board: FlightController | null = null

  firmware_info: FirmwareInfo | null = null

  vehicle_type: string | null = null

  firmware_vehicle_type: FirmwareVehicleType | null = null

  sitl_frame: SITLFrame | null = null

  updating_endpoints = true

  updating_boards = true

  restarting = false

  autopilot_serials: SerialEndpoint[] = []

  // All vehicle types include the values ArduSub overloaded for legacy lights support, so we need to filter by it
  get lights1_servo_function(): number {
    const is_sub = this.firmware_vehicle_type === FirmwareVehicleType.ArduSub
    const version = this.firmware_info?.version
    if (is_sub && version && sem_ver_lte(version, LEGACY_SUB_LIGHTS_MAX_VERSION)) {
      return LEGACY_SUB_LIGHTS1
    }
    return SUB_SERVO_FUNCTION.LIGHTS1
  }

  get lights2_servo_function(): number {
    const is_sub = this.firmware_vehicle_type === FirmwareVehicleType.ArduSub
    const version = this.firmware_info?.version
    if (is_sub && version && sem_ver_lte(version, LEGACY_SUB_LIGHTS_MAX_VERSION)) {
      return LEGACY_SUB_LIGHTS2
    }
    return SUB_SERVO_FUNCTION.LIGHTS2
  }

  @Mutation
  setAutopilotSerialConfigurations(serials: SerialEndpoint[]): void {
    this.autopilot_serials = serials
  }

  @Mutation
  setRestarting(restarting: boolean): void {
    this.restarting = restarting
  }

  @Mutation
  setUpdatingEndpoints(updating: boolean): void {
    this.updating_endpoints = updating
  }

  @Mutation
  setCurrentBoard(board: FlightController | null): void {
    this.current_board = board
  }

  @Mutation
  setFirmwareInfo(firmware_info: FirmwareInfo | null): void {
    this.firmware_info = firmware_info
  }

  @Mutation
  setVehicleType(vehicle_type: string | null): void {
    this.vehicle_type = vehicle_type
  }

  @Mutation
  setFirmwareVehicleType(firmware_vehicle_type: FirmwareVehicleType | null): void {
    this.firmware_vehicle_type = firmware_vehicle_type
  }

  @Mutation
  setSitlFrame(sitl_frame: SITLFrame | null): void {
    // UNDEFINED means "no frame selected" — collapse it to null so consumers
    // (e.g. the SITL <v-select>) have a single sentinel to handle.
    this.sitl_frame = sitl_frame === SITLFrame.UNDEFINED ? null : sitl_frame
  }

  @Mutation
  setAvailableEndpoints(available_endpoints: AutopilotEndpoint[]): void {
    this.available_endpoints = available_endpoints
    this.updating_endpoints = false
  }

  @Mutation
  setAvailableBoards(boards: FlightController[]): void {
    this.available_boards = boards
    this.updating_boards = false
  }
}

export { AutopilotManagerStore }

const autopilot: AutopilotManagerStore = getModule(AutopilotManagerStore)
export default autopilot
