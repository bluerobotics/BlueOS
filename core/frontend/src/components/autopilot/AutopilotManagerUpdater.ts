import { AxiosResponse } from 'axios'
import { SemVer } from 'semver'

import Notifier from '@/libs/notifier'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { Firmware, SITLFrame, Vehicle } from '@/types/autopilot'
import { Dictionary } from '@/types/common'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(autopilot_service)

export interface FirmwareInstallLog {
  stream: string
  data: string
}

export function parseFirmwareInstallLines(lines: string[]): FirmwareInstallLog[] {
  return lines.filter((line) => line.trim()).flatMap((line) => {
    try {
      return [JSON.parse(line) as FirmwareInstallLog]
    } catch (error) {
      console.error('Failed to parse firmware install log line:', line, error)
      return []
    }
  })
}

// The backend ends every install stream with a control line, 'done' on success or 'error' on failure
export function firmwareInstallResult(logs: FirmwareInstallLog[]): string | null {
  const last_log = logs.last()
  return last_log?.stream === 'control' ? last_log.data : null
}

export function lastFirmwareInstallError(logs: FirmwareInstallLog[]): string | undefined {
  return logs.filter((log) => log.stream === 'stderr').last()?.data
}

export async function readFirmwareInstallStream(
  response: Response,
  on_logs: (logs: FirmwareInstallLog[]) => void,
): Promise<FirmwareInstallLog[]> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }
  const decoder = new TextDecoder()
  const all_logs: FirmwareInstallLog[] = []
  let buffer = ''
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read()
    buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    // Keep the last incomplete line in the buffer until the stream ends
    buffer = done ? '' : lines.pop() ?? ''
    const logs = parseFirmwareInstallLines(lines)
    if (logs.length > 0) {
      all_logs.push(...logs)
      on_logs(logs)
    }
    if (done) {
      return all_logs
    }
  }
}

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
      url: `${autopilot.API_URL_V2}/available_boards`,
      timeout: 30000,
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
    url: `${autopilot.API_URL_V2}/board`,
    timeout: 30000,
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
      timeout: 30000,
    })
    // Version comes out as a string, let's turn it into a SemVer object
    response.data.version = new SemVer(response.data.version)
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
      timeout: 30000,
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

export async function fetchSitlFrame(): Promise<void> {
  try {
    const response: AxiosResponse = await back_axios({
      method: 'get',
      url: `${autopilot.API_URL}/sitl_frame`,
      timeout: 10000,
    })
    autopilot.setSitlFrame(response.data as SITLFrame)
  } catch (error) {
    autopilot.setSitlFrame(null)
    notifier.pushBackError('AUTOPILOT_SITL_FRAME_FETCH_FAIL', error)
  }
}

export async function availableFirmwares(vehicleType: Vehicle): Promise<Firmware[]> {
  return back_axios({
    method: 'get',
    url: `${autopilot.API_URL}/available_firmwares`,
    timeout: 60000,
    params: {
      vehicle: vehicleType,
    },
  })
    .then((response) => response.data)
    .catch((error) => {
      const message = `Failed to fetch available firmwares for vehicle (${vehicleType}): ${error.message}`
      notifier.pushError('AUTOPILOT_FIRMWARE_AVAILABLES_FAIL', message)
      throw new Error(error)
    })
}

export async function installFirmwareFromUrl(
  url: URL,
  make_default: boolean | undefined,
  default_params?: Dictionary<number>,
): Promise<void> {
  const response: AxiosResponse<string> = await back_axios({
    method: 'post',
    url: `${autopilot.API_URL}/install_firmware_from_url`,
    // Flashing a serial board alone can take up to 180 s, then the autopilot is restarted
    timeout: 300000,
    // The response is NDJSON, which must not go through axios' JSON parsing
    responseType: 'text',
    params: {
      // eslint-disable-next-line object-shorthand
      url: url,
      make_default: make_default ?? false,
    },
    data: {
      params: default_params ?? {},
    },
  })
    .catch((error) => {
      const message = `Failed to install firmware from ${url}: ${error.message}`
      notifier.pushError('AUTOPILOT_FIRMWARE_INSTALL_FAIL', message)
      throw new Error(error)
    })
  const logs = parseFirmwareInstallLines(response.data.split('\n'))
  if (firmwareInstallResult(logs) !== 'done') {
    throw new Error(lastFirmwareInstallError(logs) ?? 'Firmware installation did not complete')
  }
}

export async function restart(): Promise<void> {
  autopilot_data.reset()
  autopilot.setRestarting(true)
  return back_axios({
    method: 'post',
    url: `${autopilot.API_URL}/restart`,
    // Serial boards reboot over MAVLink and re-enumerate on USB; the backend waits for the board to
    // drop and come back before reopening the link, which can take tens of seconds.
    timeout: 60000,
  })
    .then((response) => response.data)
    .catch((error) => {
      notifier.pushBackError('AUTOPILOT_RESTART_FAIL', error)
      throw new Error(error)
    })
    .finally(() => {
      autopilot.setRestarting(false)
      autopilot_data.setRebootRequired(false)
    })
}
