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
    id?: string,
}

export interface ExtensionData {
    identifier: string
    name: string
    description: string
    docker: string
    versions: Dictionary<Version>
    extension_logo?: string
    company_logo: string
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
    id?: string
}
export interface RunningContainer {
    name: string
    image: string
    imageId: string
    status: string
}
