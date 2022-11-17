import { Dictionary } from '@/types/common'

export interface Author {
    name: string
    email: string
}

export interface Company {
    name: string
    email: string
    about: string
}

export interface Version {
    permissions: any
    requirements: string | null
    tag: string
    authors?: Author[]
    docs?: string
    support?: string
    readme?: string
    website: string
    company?: Company
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
    permissions: string
    user_permissions: string
    status?: string
}
export interface RunningContainer {
    name: string
    image: string
    imageId: string
    status: string
}
