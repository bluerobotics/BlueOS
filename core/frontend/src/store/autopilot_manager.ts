import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import {
  AutopilotEndpoint, FirmwareInfo, FirmwareVehicleType,
  FlightController, SerialEndpoint,
} from '@/types/autopilot'

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

  updating_endpoints = true

  updating_boards = true

  restarting = false

  autopilot_serials: SerialEndpoint[] = []

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
