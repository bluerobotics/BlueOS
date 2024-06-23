import filebrowser from '@/libs/filebrowser'
import { XzReadableStream } from 'xz-decompress'

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
  const px4ExtrasFolder = await filebrowser.fetchFolder('ardupilot_logs/logs/mavftp/etc/extras', 30000)

  const parameterFile = px4ExtrasFolder.items.find((file) => file.name === 'parameters.json.xz')
  if (!parameterFile) {
    throw new Error('PX4 parameters metadata file not found')
  }

  const response = await fetch(await filebrowser.singleFileRelativeURL(parameterFile))
  if (!response || !response.ok || !response.body) {
    throw new Error(`Failed to fetch PX4 parameters metadata: ${response.statusText}`)
  }

  const decompressedStream = new Response(new XzReadableStream(response.body))

  return (await decompressedStream.json()).parameters as PX4ParametersMetadata[]
}

async function fetchPX4Metadata(): Promise<PX4ParametersMetadata[]> {
  let metadata
  try {
    metadata = await fetchPX4MetadataFromBoard()
  } catch (e) {
    console.error('Falling back to default PX4 Metadata Repository parameters, unable to fetch from board.', e)
    metadata = (await import('@/PX4-parameters/master/parameters.json')).parameters
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
