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

export interface DiskSpeedResult {
  write_speed_mbps: number | null
  read_speed_mbps: number | null
  bytes_tested: number
  seed: string
  success: boolean
  error: string | null
}

export interface DiskSpeedTestPoint {
  size_mb: number
  write_speed: number | null
  read_speed: number | null
  total_tests?: number
}
