import { isNumber } from 'lodash'

import { fetchVehicleType } from '@/components/autopilot/AutopilotManagerUpdater'
import { MavAutopilot } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { Dictionary } from '@/types/common'

import Parameter from './parameter'
import { fetchPX4Metadata, PX4ParametersMetadata } from './px4/metadata-fetcher'
import { fetchFirmwareVehicleType } from '@/components/autopilot/AutopilotManagerUpdater'
import { FirmwareVehicleType } from '@/types/autopilot'
import axios from 'axios'

// Parameter metadata as in the JSON files
interface Metadata {
  Description?: string
  DisplayName: string
  Increment?: string
  Range?: {
    high: string
    low: string
  }
  RebootRequired?: string,
  ReadOnly?: string,
  Bitmask?: {[key:number] : string}
  Values?: {[key:number] : string}
  User?: string
  Units?: string
  Default?: string
}

interface MetadataCategory {
  [key: string]: Metadata | number; // number deals with a sneaky {"json": 0} entry
}
interface MetadataFile {
    [key: string]: MetadataCategory;
}

function fromPX4toArduPilotParametersMetadata(parameters: PX4ParametersMetadata[]): Record<string, Metadata> {
  return parameters.reduce((acc, param) => {
    acc[param.name] = {
      User: param.category,
      Description: param.longDesc ?? param.shortDesc,
      DisplayName: param.shortDesc,
      ...param.max && param.min && { Range: { high: param.max.toString(), low: param.min.toString() } },
      ...param.rebootRequire && { RebootRequired: param.rebootRequire ? 'True' : 'False' },
      ...param.units && { Units: param.units },
    }

    // In case default is like 1.0 and got loaded as 1 but should be a float
    if (Number.isInteger(param.default) && param.type === 'Float') {
      acc[param.name].Default = param.default.toFixed(1)
    } else {
      acc[param.name].Default = param.default.toString()
    }

    if (param.increment) {
      // In case increment is like 1.0 and got loaded as 1 but should be a float
      if (Number.isInteger(param.increment) && param.type === 'Float') {
        acc[param.name].Increment = param.increment.toFixed(1)
      } else {
        acc[param.name].Increment = param.increment.toString()
      }
    }

    if (param.values) {
      acc[param.name].Values = param.values.reduce((valuesAcc, val) => {
        valuesAcc[val.value] = val.description
        return valuesAcc
      }, {} as Record<number, string>)
    }

    if (param.bitmask) {
      acc[param.name].Bitmask = param.bitmask.reduce((bitmaskAcc, val) => {
        bitmaskAcc[val.index] = val.description
        return bitmaskAcc
      }, {} as Record<number, string>)
    }

    return acc
  }, {} as Record<string, Metadata>)
}

export default class ParametersTable {
  parametersDict: {[key: number] : Parameter} = {}

  metadata_loaded = false

  metadata = {} as Dictionary<Metadata>

  constructor() {
    this.fetchMetadata()
  }

  reset(): void {
    this.parametersDict = {}
    this.fetchMetadata()
  }

  async fetchArduPilotMetadata(): Promise<MetadataFile | string> {
    await fetchFirmwareVehicleType() // required to populate autopilot.vehicle_type
    const jsons = Object.keys(await import.meta.glob('/public/assets/ArduPilot-Parameter-Repository/**/*.json')) as string[]
    let folder = "Copter"
    switch (autopilot.firmware_vehicle_type) {
      case FirmwareVehicleType.ArduSub:
        folder = 'Sub'
        break
      case FirmwareVehicleType.ArduRover:
        folder = 'Rover'
        break
      case FirmwareVehicleType.ArduPlane:
        folder = 'Plane'
    }
    const major = autopilot.firmware_info?.version.major
    let minor = autopilot.firmware_info?.version.minor ?? 0
    while (minor >= 0) {
      // go down one minor version at a time until we find a match
      const metadata_path = `/assets/ArduPilot-Parameter-Repository/${folder}-${major}.${minor}/apm.pdef.json`
      if (jsons.includes(`/public${metadata_path}`)) {
        return await axios.get(metadata_path).then(response => response.data as MetadataFile)
      }
      minor -= 1;
    }
    // if we didn't find a match, just return the first one. that must be better than nothing, right?
    const fallback = jsons[0].replace('/public', '')
    console.warn(`Could not find metadata for ${folder}-${major}.X. Falling back to ${fallback}`)
    return axios.get(fallback).then(response => response.data as MetadataFile)
  }


  async fetchMetadata(): Promise<void> {
    if (autopilot.vehicle_type === null) {
      // Check again later if we have a vehicle type identified
      fetchVehicleType()
      setTimeout(() => { this.fetchMetadata() }, 1000)
      return
    }

    if (autopilot_data.autopilot_type === MavAutopilot.MAV_AUTOPILOT_PX4) {
      this.metadata = fromPX4toArduPilotParametersMetadata(await fetchPX4Metadata())
    } else {
    let metadata = await this.fetchArduPilotMetadata()

      for (const category of Object.values(metadata)) {
        for (const [name, parameter] of Object.entries(category)) {
          if (isNumber(parameter)) { // ignore "json" entry
            console.log(`ignoring ${name} : ${parameter}`)
            continue
          }
          this.metadata[name] = parameter
        }
      }
    }

    this.updateParameters()
    this.metadata_loaded = true
  }

  updateParameters(): void {
    for (const parameter of Object.values(this.parametersDict)) {
      this.addParam(parameter)
    }
  }

  addParam(param: Parameter): void {
    if (param.name in this.metadata) {
      param.description = this.metadata[param.name].Description?.toTitle() ?? ''
      param.shortDescription = this.metadata[param.name].DisplayName
      param.units = this.metadata[param.name].Units
      const {
        Values, Bitmask, ReadOnly, Increment, RebootRequired, Range, Default,
      } = this.metadata[param.name]
      param.options = Values
      param.bitmask = Bitmask
      param.readonly = ReadOnly === 'True'
      param.increment = Increment ? parseFloat(Increment) : undefined
      param.rebootRequired = RebootRequired === 'True'
      param.range = Range ? { high: parseFloat(Range.high), low: parseFloat(Range.low) } : undefined
      param.default = Default ? parseFloat(Default) : undefined
    }
    this.parametersDict[param.id] = param
  }

  updateParam(param_name: string, param_value: number): void {
    const index = Object.entries(this.parametersDict).find(([_key, value]) => value.name === param_name)
    if (!index) {
      // This is benign and will happen if we receive a parameter update before the parameters table
      // is fully populated. We can safely ignore it.
      console.info(`Unable to update param in store: ${param_name}. Parameter not yet loaded into ParametersTable.`)
      return
    }
    this.parametersDict[parseInt(index[0], 10)].value = param_value
  }

  parameters(): Parameter[] {
    return Object.values(this.parametersDict)
  }

  size(): number {
    return this.parameters().length
  }

  loaded(): boolean {
    return this.metadata_loaded
  }
}
