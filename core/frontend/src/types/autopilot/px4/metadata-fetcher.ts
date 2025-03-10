interface PX4ParametersMetadataValuesItem {
  description: string
  value: number
}

interface PX4ParametersMetadataBitmaskItem {
  description: string
  index: number
}

interface PX4ParametersMetadata {
  name: string
  category: string
  group: string
  type: string

  shortDesc: string
  longDesc?: string

  default: number
  max?: number
  min?: number
  increment?: number
  units?: string

  values?: PX4ParametersMetadataValuesItem[]
  bitmask?: PX4ParametersMetadataBitmaskItem[]

  decimalPlaces?: number
  volatile?: boolean
  rebootRequire?: boolean
}

async function fetchPX4MetadataFromBoard(): Promise<PX4ParametersMetadata[]> {
  // TODO - Add mav ftp fetch to get parameters.json from board
  throw new Error('Not implemented')
}

async function fetchPX4Metadata(): Promise<PX4ParametersMetadata[]> {
  let metadata
  try {
    metadata = await fetchPX4MetadataFromBoard()
  } catch (e) {
    const response = await fetch('/PX4-parameters/master/parameters.json');
    if (!response.ok) {
      throw new Error(`Failed to fetch PX4 metadata: ${response.statusText}`);
    }
    metadata = (await response.json()).parameters;
  }

  return metadata as PX4ParametersMetadata[]
}

export {
  fetchPX4Metadata,
  fetchPX4MetadataFromBoard,
  PX4ParametersMetadata,
  PX4ParametersMetadataBitmaskItem,
  PX4ParametersMetadataValuesItem,
}
