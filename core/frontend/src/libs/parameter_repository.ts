import {
  coerce, eq as sem_ver_eq, lte as sem_ver_lte, rcompare as sem_ver_rcompare, SemVer,
} from 'semver'

import type { FlightController } from '@/types/autopilot'
import { fetchWithVehicleFallback } from '@/utils/helper_functions'

const PARAM_SETS_URL = 'https://docs.bluerobotics.com/Blueos-Parameter-Repository/params_v1.json'

export type ParamSets = Record<string, Record<string, number>>

let pending_param_sets: Promise<ParamSets> | undefined

// Keys look like "params/ardupilot/ArduSub/4.5/navigator/Standard BlueROV2.params". Everything else in the
// repository is an %include fragment or a hardware snippet, not a set a user can pick.
function parseParamSetKey(key: string): { vehicle: string, version: SemVer, board: string } | null {
  const segments = key.split('/')
  if (segments.length !== 6) {
    return null
  }
  const [, , vehicle, version, board] = segments
  const parsed_version = coerce(version)
  return parsed_version === null
    ? null
    : { vehicle: vehicle.toLowerCase(), version: parsed_version, board: board.toLowerCase() }
}

function isParamSet(value: unknown): boolean {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

// Unrecognized entries are dropped so an upstream layout change leaves an empty map, which callers read as
// "no data" rather than as a repository where every firmware looks uncurated.
export function parseParamSets(payload: unknown): ParamSets {
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    throw new Error('Parameter repository response is not an object')
  }
  return Object.fromEntries(
    Object.entries(payload).filter(([key, value]) => parseParamSetKey(key) !== null && isParamSet(value)),
  )
}

// Callers retry on failure, so errors are propagated instead of swallowed.
export async function fetchParamSets(): Promise<ParamSets> {
  try {
    pending_param_sets ??= fetchWithVehicleFallback(PARAM_SETS_URL).then((response) => response.json()).then(parseParamSets)
    return await pending_param_sets
  } catch (error) {
    pending_param_sets = undefined
    throw error
  }
}

// Directories are named after the platform, not the name, which is whatever the USB descriptor reports
// ("PX4 FMU v2.x" for a Pixhawk1). SITL is the only platform carrying a host arch suffix the repository lacks.
function boardDirectory(board: FlightController): string {
  const platform = board.platform.toLowerCase()
  return platform.startsWith('sitl') ? 'sitl' : platform
}

export function paramSetsForFirmware(
  all_param_sets: ParamSets,
  vehicle_type: string | null,
  version: SemVer | null,
  board: FlightController | null,
): ParamSets {
  if (vehicle_type === null || version === null || board === null) {
    return {}
  }
  const wanted_vehicle = vehicle_type.toLowerCase()
  const wanted_board = boardDirectory(board)

  const candidates: { key: string, version: SemVer }[] = []
  for (const key of Object.keys(all_param_sets)) {
    const parsed = parseParamSetKey(key)
    if (parsed === null || parsed.vehicle !== wanted_vehicle || parsed.board !== wanted_board) {
      continue
    }
    // Sets carry forward until a newer one is curated, but never across a major that may rename parameters
    if (parsed.version.major === version.major && sem_ver_lte(parsed.version, version)) {
      candidates.push({ key, version: parsed.version })
    }
  }
  if (candidates.length === 0) {
    return {}
  }

  const [newest] = candidates.map((candidate) => candidate.version).sort(sem_ver_rcompare)
  return Object.fromEntries(
    candidates
      .filter((candidate) => sem_ver_eq(candidate.version, newest))
      .map((candidate) => [candidate.key, all_param_sets[candidate.key]]),
  )
}
