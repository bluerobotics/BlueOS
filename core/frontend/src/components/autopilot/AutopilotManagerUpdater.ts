import { AxiosResponse } from 'axios'

import Notifier from '@/libs/notifier'
import autopilot from '@/store/autopilot_manager'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(autopilot_service)

export async function fetchAutopilotSerialConfiguration(): Promise<void> {
  await back_axios({
    method: 'get',
    url: `${autopilot.API_URL}/serials`,
    timeout: 10000,
  })
    .then((response) => {
      const available_endpoints = response.data
      autopilot.setAutopilotSerialConfigurations(available_endpoints)
    })
    .catch((error) => {
      autopilot.setAutopilotSerialConfigurations([])
      notifier.pushBackError('AUTOPILOT_ENDPOINT_FETCH_FAIL', error)
    })
}

export async function fetchAvailableEndpoints(): Promise<void> {
  try {
    const response = await back_axios({
      method: 'get',
      url: `${autopilot.API_URL}/endpoints`,
      timeout: 10000,
    })
    const available_endpoints = response.data
    autopilot.setAvailableEndpoints(available_endpoints)
  } catch (error) {
    autopilot.setAvailableEndpoints([])
    notifier.pushBackError('AUTOPILOT_ENDPOINT_FETCH_FAIL', error)
  }
}
export async function fetchAvailableBoards(): Promise<void> {
  try {
    const response: AxiosResponse = await back_axios({
      method: 'get',
      url: `${autopilot.API_URL}/available_boards`,
      timeout: 10000,
    })
    autopilot.setAvailableBoards(response.data)
  } catch (error) {
    autopilot.setAvailableBoards([])
    notifier.pushBackError('AUTOPILOT_BOARDS_FETCH_FAIL', error)
  }
}

export async function fetchCurrentBoard(): Promise<void> {
  await back_axios({
    method: 'get',
    url: `${autopilot.API_URL}/board`,
    timeout: 10000,
  })
    .then((response) => {
      autopilot.setCurrentBoard(response.data)
    })
    .catch((error) => {
      autopilot.setCurrentBoard(null)
      notifier.pushBackError('AUTOPILOT_BOARD_FETCH_FAIL', error)
    })
}

export async function fetchFirmwareInfo(): Promise<void> {
  try {
    const response: AxiosResponse = await back_axios({
      method: 'get',
      url: `${autopilot.API_URL}/firmware_info`,
      timeout: 10000,
    })
    autopilot.setFirmwareInfo(response.data)
  } catch (error) {
    autopilot.setFirmwareInfo(null)
    notifier.pushBackError('AUTOPILOT_FIRM_INFO_FETCH_FAIL', error)
  }
}

export async function fetchVehicleType(): Promise<void> {
  try {
    const response: AxiosResponse = await back_axios({
      method: 'get',
      url: `${autopilot.API_URL}/vehicle_type`,
      timeout: 10000,
    })
    autopilot.setVehicleType(response.data)
  } catch (error) {
    autopilot.setVehicleType(null)
    notifier.pushBackError('AUTOPILOT_VEHICLE_TYPE_FETCH_FAIL', error)
  }
}

export async function fetchFirmwareVehicleType(): Promise<void> {
  try {
    const response: AxiosResponse = await back_axios({
      method: 'get',
      url: `${autopilot.API_URL}/firmware_vehicle_type`,
      timeout: 10000,
    })
    autopilot.setFirmwareVehicleType(response.data)
  } catch (error) {
    autopilot.setFirmwareVehicleType(null)
    notifier.pushBackError('AUTOPILOT_FIRMWARE_VEHICLE_TYPE_FETCH_FAIL', error)
  }
}
