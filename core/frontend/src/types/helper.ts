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

export interface SpeedtestServer {
    url: string
    lat: string
    lon: string
    name: string
    country: string
    cc: string
    sponsor: string
    id: string
    host: string
    d: number
    latency: number
}

export interface SpeedtestClient {
    ip: string
    lat: string
    lon: string
    isp: string
    isprating: string
    rating: string
    ispdlavg: string
    ispulavg: string
    loggedin: string
    country: string
}

export interface SpeedTestResult {
    download: number
    upload: number
    ping: number
    server: SpeedtestServer
    timestamp: Date
    bytes_sent: number
    bytes_received: number
    share: string | null
    client: SpeedtestClient
}
