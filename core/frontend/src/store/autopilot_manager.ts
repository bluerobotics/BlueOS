import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { AutopilotEndpoint, FirmwareInfo, FlightController } from '@/types/autopilot'

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

  updating_endpoints = true

  updating_boards = true

  restarting = false

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
  setAvailableEndpoints(available_endpoints: AutopilotEndpoint[]): void {
    this.available_endpoints = available_endpoints
    this.updating_endpoints = false
  }

  @Mutation
  setAvailableBoards(available_boards: FlightController[]): void {
    this.available_boards = available_boards
    this.updating_boards = false
  }
}

export { AutopilotManagerStore }

const autopilot: AutopilotManagerStore = getModule(AutopilotManagerStore)
export default autopilot
