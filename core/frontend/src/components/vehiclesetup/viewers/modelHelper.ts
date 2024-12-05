import autopilot_data from "@/store/autopilot"
import autopilot from "@/store/autopilot_manager"

import {
    FRAME_TYPE as ROVER_FRAME_TYPE,
  } from '@/types/autopilot/parameter-rover-enums'

import {
    BTN_FUNCTION as SUB_BTN_FUNCTION,
    FRAME_CONFIG as SUB_FRAME_CONFIG,
    SERVO_FUNCTION as SUB_SERVO_FUNCTION,
  } from '@/types/autopilot/parameter-sub-enums'
import { sleep } from "@/utils/helper_functions"
import axios from "axios"

const models: Record<string, string> = import.meta.glob('/public/assets/vehicles/models/**', { eager: true })

function vehicle_folder(): string {
switch (autopilot.vehicle_type) {
    case 'Submarine':
    return 'sub'
    case 'Surface Boat':
    return 'boat'
    case 'Ground Rover':
    return 'rover'
    default:
    return ''
}
}

export enum BoardName {
    NAVIGATOR = 'NAVIGATOR',
    GENERIC = 'GENERIC',
}


function frame_type(): number | undefined {
    switch (autopilot.vehicle_type) {
      case 'Submarine':
        return autopilot_data.parameter('FRAME_CONFIG')?.value
      case 'Surface Boat':
        return autopilot_data.parameter('FRAME_TYPE')?.value
        // TODO: other vehicles
      default:
        return undefined
    }
  }


export function frame_name(): string | undefined {
    let result
    switch (autopilot.vehicle_type) {
      case 'Submarine':
        result = Object.entries(SUB_FRAME_CONFIG).find((key, value) => value === frame_type())?.[1] as string
        break
      case 'Surface Boat':
        // we already know it is a boat, so check only TYPE and ignore CLASS (rover/boat/balancebot)
        result = Object.entries(ROVER_FRAME_TYPE).find((key, value) => value === frame_type())?.[1] as string
        break
      case 'Ground Rover':
        // TOOD: check FRAME_TYPE
        result = 'unknown'
        break
        // TODO: other vehicles
      default:
        break
    }
    return result ? `${result}` : undefined
  }

export async function checkModelOverrides() {
    while (!autopilot.vehicle_type) {
      await sleep(100)
    }
    const master_override = '/userdata/modeloverrides/ALL.glb'
    const vehicle_override = `/userdata/modeloverrides/${vehicle_folder()}/${frame_name()}.glb`
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

  export function get_model(): undefined | string {
    const release_path = `assets/vehicles/models/${vehicle_folder()}/${frame_name()}.glb`
    if (models[`/public/${release_path}`]) {
      return `/assets/vehicles/models/${vehicle_folder()}/${frame_name()}.glb`
    }
    return undefined
  }
  
  export async function get_board_model(board?: string): Promise<string> {
    if (board === "Navigator") {
      return await import('@/assets/3d/navigator.glb')
    }
    console.log(`No 3D model for board ${board}`)
    return await import('@/assets/3d/generic_sensor.glb')
  }
