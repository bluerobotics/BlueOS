export interface ThemeStatus {
    primary: string
    palette: Record<string, string>
    css_url: string
}

export interface ModelEntry {
    name: string
    size_bytes: number
    url: string
}

export interface BrandingAsset {
    url: string | null
    size_bytes: number | null
}
