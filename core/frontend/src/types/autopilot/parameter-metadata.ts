export interface ParameterMetadata {
  Description?: string
  DisplayName?: string
  Increment?: string
  Range?: {
    high?: string
    low?: string
  }
  RebootRequired?: string
  ReadOnly?: string
  Bitmask?: { [key: number]: string }
  Values?: { [key: number]: string }
  User?: string
  Units?: string
  Default?: string
}

export interface ArduPilotMetadataFile {
  [key: string]: {
    [key: string]: ParameterMetadata | number
  }
}

interface ComponentParameterValue {
  value: number
  description: string
}

interface ComponentParameterBit {
  index: number
  description: string
}

interface ComponentParameterMetadata {
  name: string
  shortDesc?: string
  longDesc?: string
  default?: number
  min?: number
  max?: number
  increment?: number
  readOnly?: boolean
  rebootRequired?: boolean
  values?: ComponentParameterValue[]
  bitmask?: ComponentParameterBit[]
  units?: string
}

interface ComponentParameterMetadataFile {
  version: number
  parameters: ComponentParameterMetadata[]
}

export type ParameterMetadataTable = Record<string, ParameterMetadata>

export interface ComponentMetadataState {
  metadata: ParameterMetadataTable
  etag?: string
}

export interface ComponentMetadataStateUpdate extends ComponentMetadataState {
  changed: boolean
}

const ARDUPILOT_METADATA_PATH = '/assets/ArduPilot-Parameter-Repository/'

export function selectArduPilotMetadataPath(
  paths: string[],
  folder: string,
  major: number | undefined,
  minor: number,
): string {
  if (major !== undefined) {
    for (let candidateMinor = minor; candidateMinor >= 0; candidateMinor -= 1) {
      const candidate = `${ARDUPILOT_METADATA_PATH}${folder}-${major}.${candidateMinor}/apm.pdef.json`
      if (paths.includes(`/public${candidate}`)) return candidate
    }
  }

  const sameVehicle = paths
    .map((path) => {
      const match = path.match(new RegExp(`/${folder}-(\\d+)\\.(\\d+)/apm\\.pdef\\.json$`))
      return match === null ? undefined : {
        path: path.replace('/public', ''),
        major: Number(match[1]),
        minor: Number(match[2]),
      }
    })
    .filter((candidate): candidate is { path: string; major: number; minor: number } => candidate !== undefined)
    .sort((left, right) => right.major - left.major || right.minor - left.minor)

  if (sameVehicle.length > 0) return sameVehicle[0].path
  if (paths.length === 0) throw new Error('No bundled ArduPilot parameter metadata is available')
  return paths[0].replace('/public', '')
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function optionalString(value: Record<string, unknown>, field: string): string | undefined {
  const fieldValue = value[field]
  if (fieldValue !== undefined && typeof fieldValue !== 'string') {
    throw new Error(`Parameter metadata field ${field} must be a string`)
  }
  return fieldValue as string | undefined
}

function optionalNumber(value: Record<string, unknown>, field: string): number | undefined {
  const fieldValue = value[field]
  if (fieldValue !== undefined && !isFiniteNumber(fieldValue)) {
    throw new Error(`Parameter metadata field ${field} must be a finite number`)
  }
  return fieldValue as number | undefined
}

function optionalBoolean(value: Record<string, unknown>, field: string): boolean | undefined {
  const fieldValue = value[field]
  if (fieldValue !== undefined && typeof fieldValue !== 'boolean') {
    throw new Error(`Parameter metadata field ${field} must be a boolean`)
  }
  return fieldValue as boolean | undefined
}

function parseValueList(value: unknown): ComponentParameterValue[] | undefined {
  if (value === undefined) return undefined
  if (!Array.isArray(value)) throw new Error('Parameter values must be an array')

  return value.map((entry) => {
    if (!isRecord(entry) || !isFiniteNumber(entry.value) || typeof entry.description !== 'string') {
      throw new Error('Parameter value entry is invalid')
    }
    return { value: entry.value, description: entry.description }
  })
}

function parseBitmask(value: unknown): ComponentParameterBit[] | undefined {
  if (value === undefined) return undefined
  if (!Array.isArray(value)) throw new Error('Parameter bitmask must be an array')

  return value.map((entry) => {
    if (!isRecord(entry) || !isFiniteNumber(entry.index) || typeof entry.description !== 'string') {
      throw new Error('Parameter bitmask entry is invalid')
    }
    return { index: entry.index, description: entry.description }
  })
}

function parseComponentParameter(value: unknown): ComponentParameterMetadata {
  if (!isRecord(value) || typeof value.name !== 'string' || value.name.length === 0) {
    throw new Error('Parameter metadata entry is missing a name')
  }

  return {
    name: value.name,
    shortDesc: optionalString(value, 'shortDesc'),
    longDesc: optionalString(value, 'longDesc'),
    default: optionalNumber(value, 'default'),
    min: optionalNumber(value, 'min'),
    max: optionalNumber(value, 'max'),
    increment: optionalNumber(value, 'increment'),
    readOnly: optionalBoolean(value, 'readOnly'),
    rebootRequired: optionalBoolean(value, 'rebootRequired'),
    values: parseValueList(value.values),
    bitmask: parseBitmask(value.bitmask),
    units: optionalString(value, 'units'),
  }
}

function parseComponentMetadata(value: unknown): ComponentParameterMetadataFile {
  if (!isRecord(value)
    || !isFiniteNumber(value.version)
    || !Number.isInteger(value.version)
    || value.version < 3
    || !Array.isArray(value.parameters)) {
    throw new Error('Component parameter metadata document is invalid')
  }
  return {
    version: value.version,
    parameters: value.parameters.map(parseComponentParameter),
  }
}

function valuesToRecord(values: ComponentParameterValue[]): { [key: number]: string } {
  return Object.fromEntries(values.map(({ value, description }) => [value, description]))
}

function bitmaskToRecord(bits: ComponentParameterBit[]): { [key: number]: string } {
  return Object.fromEntries(bits.map(({ index, description }) => [index, description]))
}

function normalizeComponentParameter(parameter: ComponentParameterMetadata): ParameterMetadata {
  const metadata: ParameterMetadata = {}
  if (parameter.shortDesc !== undefined) metadata.DisplayName = parameter.shortDesc
  if (parameter.longDesc !== undefined) metadata.Description = parameter.longDesc
  if (parameter.default !== undefined) metadata.Default = parameter.default.toString()
  if (parameter.increment !== undefined) metadata.Increment = parameter.increment.toString()
  if (parameter.units !== undefined) metadata.Units = parameter.units
  if (parameter.readOnly !== undefined) metadata.ReadOnly = parameter.readOnly ? 'True' : 'False'
  if (parameter.rebootRequired !== undefined) {
    metadata.RebootRequired = parameter.rebootRequired ? 'True' : 'False'
  }
  if (parameter.min !== undefined || parameter.max !== undefined) {
    metadata.Range = {
      ...parameter.min !== undefined && { low: parameter.min.toString() },
      ...parameter.max !== undefined && { high: parameter.max.toString() },
    }
  }
  if (parameter.values !== undefined) metadata.Values = valuesToRecord(parameter.values)
  if (parameter.bitmask !== undefined) metadata.Bitmask = bitmaskToRecord(parameter.bitmask)
  return metadata
}

export function flattenArduPilotMetadata(metadata: ArduPilotMetadataFile): ParameterMetadataTable {
  const flattened: ParameterMetadataTable = {}
  for (const category of Object.values(metadata)) {
    for (const [name, parameter] of Object.entries(category)) {
      if (typeof parameter === 'number') continue
      flattened[name] = parameter
    }
  }
  return flattened
}

export function normalizeComponentMetadata(metadata: unknown): ParameterMetadataTable {
  const normalized: ParameterMetadataTable = {}
  for (const parameter of parseComponentMetadata(metadata).parameters) {
    normalized[parameter.name] = normalizeComponentParameter(parameter)
  }
  return normalized
}

export function updateComponentMetadataState(
  current: ComponentMetadataState,
  status: number,
  document?: unknown,
  etag?: string,
): ComponentMetadataStateUpdate {
  if (status === 304) return { ...current, changed: false }
  if (status === 204) {
    const changed = current.etag !== undefined || Object.keys(current.metadata).length > 0
    return { metadata: {}, etag: undefined, changed }
  }
  if (status !== 200) throw new Error(`Unsupported parameter metadata response status ${status}`)
  if (etag !== undefined && etag === current.etag) return { ...current, changed: false }
  return { metadata: normalizeComponentMetadata(document), etag, changed: true }
}

function cloneMetadata(metadata: ParameterMetadata): ParameterMetadata {
  return {
    ...metadata,
    ...metadata.Range && { Range: { ...metadata.Range } },
    ...metadata.Values && { Values: { ...metadata.Values } },
    ...metadata.Bitmask && { Bitmask: { ...metadata.Bitmask } },
  }
}

function templatePattern(name: string): RegExp | undefined {
  if (!name.includes('{n}')) return undefined
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`^${escaped.replace(/\\\{n\\\}/g, '\\d+')}$`)
}

export function metadataForParameter(
  metadata: ParameterMetadataTable,
  parameterName: string,
): ParameterMetadata | undefined {
  if (metadata[parameterName] !== undefined) return metadata[parameterName]
  return Object.entries(metadata).find(([name]) => templatePattern(name)?.test(parameterName))?.[1]
}

export function mergedMetadataForParameter(
  bundled: ParameterMetadataTable,
  component: ParameterMetadataTable,
  parameterName: string,
): ParameterMetadata | undefined {
  const bundledMetadata = metadataForParameter(bundled, parameterName)
  const componentMetadata = metadataForParameter(component, parameterName)
  if (bundledMetadata === undefined && componentMetadata === undefined) return undefined
  return mergeMetadata(bundledMetadata, componentMetadata)
}

function mergeMetadata(
  bundled: ParameterMetadata | undefined,
  component: ParameterMetadata | undefined,
): ParameterMetadata {
  return {
    ...bundled && cloneMetadata(bundled),
    ...component && cloneMetadata(component),
    ...component?.Range && { Range: { ...bundled?.Range, ...component.Range } },
  }
}

export function mergeParameterMetadata(
  bundled: ParameterMetadataTable,
  component: ParameterMetadataTable,
): ParameterMetadataTable {
  const merged = Object.fromEntries(
    Object.entries(bundled).map(([name, metadata]) => [name, cloneMetadata(metadata)]),
  )

  for (const [name, metadata] of Object.entries(component)) {
    merged[name] = mergeMetadata(merged[name], metadata)
  }
  return merged
}
