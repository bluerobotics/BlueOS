import { Dictionary, JSONValue } from '@/types/common'

export interface Author {
    name: string
    email: string
}

export interface Company {
    name: string
    email: string
    about: string
}

export enum ExtensionType {
    DEVICE_INTEGRATION = 'device-integration',
    EXAMPLE = 'example',
    OTHER = 'other',
    TOOL = 'tool',
    THEME = 'theme',
}

export interface ImagePlatform {
    architecture: string
    variant?: string
    os?: string
}

export interface VersionImage {
    expanded_size: number
    platform: ImagePlatform
    digest: string
    compatible: boolean
}

export interface Version {
    permissions: JSONValue
    requirements: string | null
    tag: string
    authors?: Author[]
    docs?: string
    support?: string
    readme?: string
    website: string
    company?: Company
    type: ExtensionType,
    filter_tags: string[],
    images: VersionImage[]
}

export interface ExtensionData {
    identifier: string
    name: string
    description: string
    docker: string
    versions: Dictionary<Version>
    extension_logo?: string
    company_logo: string
    is_compatible?: boolean
    repo_info?: {
        downloads: number,
        last_updated?: string,
        date_registered?: string,
    }
}

export interface InstalledExtensionData {
    identifier: string
    name: string
    docker: string
    tag: string
    enabled: boolean
    permissions: string
    user_permissions: string
    status?: string
    loading?: boolean
}
export interface RunningContainer {
    name: string
    image: string
    imageId: string
    status: string
}

export interface ManifestSource {
  name: string
  url: string
  enabled: boolean
}

export interface Manifest extends ManifestSource {
  identifier: string
  priority: number
  factory: boolean
  data?: [ExtensionData]
}
