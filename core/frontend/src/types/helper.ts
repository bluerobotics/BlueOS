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
    sanitized_name?: string
    extra_query?: string
    avoid_iframes?: boolean
    works_in_relative_paths?: boolean
}

export interface Service {
    valid: boolean
    title: string
    documentation_url: string
    versions: Array<string>
    port: number
    path?: string
    metadata?: ServiceMetadata
}

// Mirrors the WebsiteError enum from
// core/services/helper/main.py
export enum WebsiteError {
  DNS = 'dns',
  TIMEOUT = 'timeout',
}

export enum InternetConnectionState {
  OFFLINE = 0,
  UNKNOWN = 1,
  LIMITED = 2,
  ONLINE = 3,
}
