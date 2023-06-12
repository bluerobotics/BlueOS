import { isNumber } from 'lodash'

import * as arducopter_metadata from '@/ArduPilot-Parameter-Repository/Copter-4.3/apm.pdef.json'
import * as ardurover_metadata from '@/ArduPilot-Parameter-Repository/Rover-4.2/apm.pdef.json'
import * as ardusub_metadata from '@/ArduPilot-Parameter-Repository/Sub-4.1/apm.pdef.json'
import { fetchVehicleType } from '@/components/autopilot/AutopilotManagerUpdater'
import autopilot from '@/store/autopilot_manager'
import { Dictionary } from '@/types/common'

import Parameter from './parameter'

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
}

interface MetadataCategory {
  [key: string]: Metadata | number; // number deals with a sneaky {"json": 0} entry
}
interface MetadataFile {
    [key: string]: MetadataCategory;
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
  }

  fetchMetadata(): void {
    if (autopilot.vehicle_type === null) {
      // Check again later if we have a vehicle type identified
      fetchVehicleType()
      setTimeout(() => { this.fetchMetadata() }, 1000)
      return
    }
    // default to submarine
    let metadata : MetadataFile = ardusub_metadata
    // This is to avoid importing a 40 lines enum from mavlink and adding a switch case with 40 cases
    if (autopilot.vehicle_type.toLowerCase().includes('copter')
      || autopilot.vehicle_type.toLowerCase().includes('rotor')) {
      metadata = arducopter_metadata
    } else if (autopilot.vehicle_type.toLowerCase().includes('rover')
      || autopilot.vehicle_type.toLowerCase().includes('boat')) {
      metadata = ardurover_metadata
    }

    for (const category of Object.values(metadata)) {
      for (const [name, parameter] of Object.entries(category)) {
        if (isNumber(parameter)) { // ignore "json" entry
          console.log(`ignoring ${name} : ${parameter}`)
          continue
        }
        this.metadata[name] = parameter
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
        Values, Bitmask, ReadOnly, Increment, RebootRequired, Range,
      } = this.metadata[param.name]
      param.options = Values
      param.bitmask = Bitmask
      param.readonly = ReadOnly === 'True'
      param.increment = Increment ? parseFloat(Increment) : undefined
      param.rebootRequired = RebootRequired === 'True'
      param.range = Range ? { high: parseFloat(Range.high), low: parseFloat(Range.low) } : undefined
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
