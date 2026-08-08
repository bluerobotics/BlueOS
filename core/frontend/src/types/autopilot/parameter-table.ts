// eslint-disable-next-line import/no-unresolved
import ardupilotParamPaths from 'virtual:ardupilot-param-index'

import { fetchVehicleType } from '@/components/autopilot/AutopilotManagerUpdater'
import { MavAutopilot } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { Dictionary } from '@/types/common'

import Parameter from './parameter'
import {
  ArduPilotMetadataFile,
  flattenArduPilotMetadata,
  mergedMetadataForParameter,
  mergeParameterMetadata,
  ParameterMetadata,
  ParameterMetadataTable,
  selectArduPilotMetadataPath,
  updateComponentMetadataState,
} from './parameter-metadata'
import { fetchPX4Metadata, PX4ParametersMetadata } from './px4/metadata-fetcher'
import { fetchFirmwareVehicleType } from '@/components/autopilot/AutopilotManagerUpdater'
import { FirmwareVehicleType } from '@/types/autopilot'
import axios from 'axios'

const COMPONENT_PARAMETER_METADATA_URL = '/ardupilot-manager/v1.0/parameter_metadata'

function fromPX4toArduPilotParametersMetadata(parameters: PX4ParametersMetadata[]): ParameterMetadataTable {
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
  }, {} as ParameterMetadataTable)
}

export default class ParametersTable {
  parametersDict: {[key: number] : Parameter} = {}

  metadata_loaded = false

  metadata = {} as Dictionary<ParameterMetadata>

  bundled_metadata: ParameterMetadataTable = {}

  component_metadata: ParameterMetadataTable = {}

  component_metadata_etag: string | undefined

  component_metadata_request: Promise<boolean> | null = null

  metadata_generation = 0

  constructor() {
    this.fetchMetadata()
  }

  reset(): void {
    this.parametersDict = {}
    this.metadata = {}
    this.bundled_metadata = {}
    this.component_metadata = {}
    this.component_metadata_etag = undefined
    this.metadata_loaded = false
    this.metadata_generation += 1
    this.fetchMetadata(this.metadata_generation)
  }

  // This owns the static BlueOS metadata lookup; it does not depend on table instance state.
  // eslint-disable-next-line class-methods-use-this
  async fetchArduPilotMetadata(): Promise<ArduPilotMetadataFile> {
    try {
      const json_metadata_override = '/userdata/metadata_override.json'
      const metadata = await axios.get(json_metadata_override).then(response => response.data as ArduPilotMetadataFile)
      console.info(`Using metadata override from ${json_metadata_override}`)
      return metadata
    } catch (error) {
      console.debug(`Metadata override not present`)
    }
    await fetchFirmwareVehicleType() // required to populate autopilot.vehicle_type
    const jsons = ardupilotParamPaths
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
    const minor = autopilot.firmware_info?.version.minor ?? 0
    const metadataPath = selectArduPilotMetadataPath(jsons, folder, major, minor)
    const requestedPath = `/assets/ArduPilot-Parameter-Repository/${folder}-${major}.${minor}/apm.pdef.json`
    if (major === undefined || metadataPath !== requestedPath) {
      console.warn(
        `Could not find exact metadata for ${folder}-${major ?? 'unknown'}.${minor}. `
        + `Falling back to ${metadataPath}`,
      )
    }
    return axios.get(metadataPath).then(response => response.data as ArduPilotMetadataFile)
  }

  async fetchMetadata(generation = this.metadata_generation): Promise<void> {
    if (autopilot.vehicle_type === null) {
      // Check again later if we have a vehicle type identified
      fetchVehicleType()
      setTimeout(() => {
        if (generation === this.metadata_generation) this.fetchMetadata(generation)
      }, 1000)
      return
    }

    let bundledMetadata: ParameterMetadataTable
    if (autopilot_data.autopilot_type === MavAutopilot.MAV_AUTOPILOT_PX4) {
      bundledMetadata = fromPX4toArduPilotParametersMetadata(await fetchPX4Metadata())
    } else {
      bundledMetadata = flattenArduPilotMetadata(await this.fetchArduPilotMetadata())
    }

    if (generation !== this.metadata_generation) return
    this.bundled_metadata = bundledMetadata
    this.rebuildMetadata()
    await this.refreshComponentMetadata()
    if (generation !== this.metadata_generation) return
    this.updateParameters()
    this.metadata_loaded = true
  }

  rebuildMetadata(): void {
    this.metadata = mergeParameterMetadata(this.bundled_metadata, this.component_metadata)
  }

  async fetchComponentMetadata(generation: number): Promise<boolean> {
    try {
      const response = await axios.get(COMPONENT_PARAMETER_METADATA_URL, {
        headers: this.component_metadata_etag ? { 'If-None-Match': this.component_metadata_etag } : undefined,
        validateStatus: (status) => [200, 204, 304].includes(status),
      })
      if (generation !== this.metadata_generation) return false

      const etag = response.headers.etag as string | undefined
      const update = updateComponentMetadataState(
        { metadata: this.component_metadata, etag: this.component_metadata_etag },
        response.status,
        response.data,
        etag,
      )
      if (!update.changed) return false

      this.component_metadata = update.metadata
      this.component_metadata_etag = update.etag
      this.rebuildMetadata()
      this.updateParameters()
      return true
    } catch (error) {
      console.debug('Vehicle parameter metadata is unavailable; using the last valid metadata snapshot.', error)
      return false
    }
  }

  async refreshComponentMetadata(): Promise<boolean> {
    if (this.component_metadata_request !== null) return this.component_metadata_request

    const generation = this.metadata_generation
    const request = this.fetchComponentMetadata(generation)
    this.component_metadata_request = request
    try {
      return await request
    } finally {
      if (this.component_metadata_request === request) this.component_metadata_request = null
    }
  }

  updateParameters(): void {
    for (const parameter of Object.values(this.parametersDict)) {
      this.addParam(parameter)
    }
  }

  addParam(param: Parameter): void {
    const updatedParam: Parameter = {
      ...param,
      description: '',
      shortDescription: '',
      units: undefined,
      options: undefined,
      bitmask: undefined,
      readonly: false,
      increment: undefined,
      rebootRequired: false,
      range: undefined,
      default: undefined,
    }
    const metadata = mergedMetadataForParameter(this.bundled_metadata, this.component_metadata, param.name)
    if (metadata !== undefined) {
      updatedParam.description = metadata.Description?.toTitle() ?? ''
      updatedParam.shortDescription = metadata.DisplayName ?? param.name
      updatedParam.units = metadata.Units
      const {
        Values, Bitmask, ReadOnly, Increment, RebootRequired, Range, Default,
      } = metadata
      updatedParam.options = Values
      updatedParam.bitmask = Bitmask
      updatedParam.readonly = ReadOnly === 'True'
      updatedParam.increment = Increment !== undefined ? parseFloat(Increment) : undefined
      updatedParam.rebootRequired = RebootRequired === 'True'
      if (Range?.high !== undefined && Range?.low !== undefined) {
        updatedParam.range = { high: parseFloat(Range.high), low: parseFloat(Range.low) }
      }
      updatedParam.default = Default !== undefined ? parseFloat(Default) : undefined
    }
    this.parametersDict[param.id] = updatedParam
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
