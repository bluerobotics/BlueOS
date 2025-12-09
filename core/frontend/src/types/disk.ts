export interface DiskNode {
  name: string
  path: string
  size_bytes: number
  is_dir: boolean
  children: DiskNode[]
}

export interface DiskUsageResponse {
  root: DiskNode
  generated_at: number
  depth: number
  include_files: boolean
  min_size_bytes: number
}

export interface DiskUsageQuery {
  path?: string
  depth?: number
  include_files?: boolean
  min_size_bytes?: number
}
