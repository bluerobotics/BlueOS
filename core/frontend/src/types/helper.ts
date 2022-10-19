export interface ServiceMetadata {
    name: string
    description: string
    icon: string
    company: string
    version: string
    webpage: string
    api: string
    route?: string
    new_page?: boolean
}

export interface Service {
    valid: boolean
    title: string
    documentation_url: string
    versions: Array<string>
    port: number
    metadata?: ServiceMetadata
}
