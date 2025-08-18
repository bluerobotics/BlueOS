import { MavType } from "@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum"
import autopilot_data from "@/store/autopilot"
import autopilot from "@/store/autopilot_manager"

import {
    FRAME_CLASS as ROVER_FRAME_CLASS,
    FRAME_TYPE as ROVER_FRAME_TYPE,
  } from '@/types/autopilot/parameter-rover-enums'

import {
    FRAME_CONFIG as SUB_FRAME_CONFIG,
  } from '@/types/autopilot/parameter-sub-enums'
import { sleep } from "@/utils/helper_functions"
import axios from "axios"

const models: Record<string, string> = import.meta.glob('/public/assets/vehicles/models/**', { eager: true })

export function vehicle_folder(): string {
  const mav_type = 'MAV_TYPE_' + autopilot.vehicle_type?.toUpperCase().replace(' ', '_')
  switch (mav_type) {
    case MavType.MAV_TYPE_SUBMARINE:
      return 'sub'
    case MavType.MAV_TYPE_SURFACE_BOAT:
    case MavType.MAV_TYPE_GROUND_ROVER:
      return 'rover'
    default:
      return autopilot.vehicle_type?.toLowerCase() || 'unknown'
  }
}

export enum BoardName {
    NAVIGATOR = 'NAVIGATOR',
    GENERIC = 'GENERIC',
}


export function frame_type(): number | undefined {
    const mav_type = 'MAV_TYPE_' + autopilot.vehicle_type?.toUpperCase()
    switch (mav_type) {
      case MavType.MAV_TYPE_SUBMARINE:
        return autopilot_data.parameter('FRAME_CONFIG')?.value
      case MavType.MAV_TYPE_SURFACE_BOAT:
        return autopilot_data.parameter('FRAME_TYPE')?.value
        // TODO: other vehicles
      default:
        return undefined
    }
  }


export function frame_name(vehicle_type: string, frame_type?: number, frame_subtype?: number): string | undefined {
    switch (vehicle_type) {
      case 'Submarine':
        return Object.entries(SUB_FRAME_CONFIG).find((key, value) => value === frame_type)?.[1] as string
      case 'Surface Boat':
      case 'Ground Rover':
        // we already know it is a boat, so check only TYPE and ignore CLASS (rover/boat/balancebot)
        return Object.entries(ROVER_FRAME_CLASS).find((key, value) => value === frame_type)?.[1] as string
     default:
        break
    }
    return undefined
  }

export async function checkModelOverrides() {
    while (!autopilot.vehicle_type || !frame_type()) {
      await sleep(100)
    }
    const master_override = '/userdata/modeloverrides/ALL.glb'
    const vehicle_override = `/userdata/modeloverrides/${vehicle_folder()}/${frame_name(autopilot.vehicle_type, frame_type())}.glb`
    try {
      await axios.head(master_override)
      return master_override
    } catch {
      console.log(`master override model not found at ${master_override}`)
    }
    try {
      await axios.head(vehicle_override)
      return vehicle_override
    } catch {
      console.log(`vehicle override model not found at ${vehicle_override}`)
    }
    return undefined
  }
  
  export async function get_board_model(board?: string): Promise<string> {
    if (board === "Navigator" || board === "Navigator64") {
      const module = await import('@/assets/3d/navigator.glb')
      return module.default
    }
    console.log(`No 3D model for board ${board}`)
    const module = await import('@/assets/3d/generic_sensor.glb')
    return module.default
  }
