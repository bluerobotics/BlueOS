export interface ResourceLimits {
  cpu_cores: number | null
  memory_mb: number | null
  io_read_mbps: number | null
  io_write_mbps: number | null
  max_pids: number | null
}

export interface ServiceState {
  name: string
  status: 'running' | 'stopped' | 'starting' | 'stopping'
  pid: number | null
  exit_code: number | null
  started_at: string | null
  stopped_at: string | null
  restart_count: number
  uptime_seconds: number | null
  command: string[]
  enabled: boolean
  restart: boolean
  env: Record<string, string>
  cwd: string | null
  restart_delay_sec: number
  stop_timeout_sec: number
  limits: ResourceLimits
}

export interface LogLine {
  timestamp: string
  stream: 'stdout' | 'stderr'
  line: string
}

export interface ServiceMetrics {
  timestamp: string
  cpu_percent: number
  memory_mb: number
  memory_peak_mb: number
  io_read_mb: number
  io_write_mb: number
  io_read_rate_mbps: number
  io_write_rate_mbps: number
  pids: number
}

export interface ServicesResponse {
  services: ServiceState[]
  count: number
}

export interface ServiceLogsResponse {
  service: string
  lines: LogLine[]
  count: number
}

export interface AllMetricsResponse {
  metrics: Record<string, ServiceMetrics>
  count: number
}

export interface ServiceMetricsResponse {
  service: string
  metrics: ServiceMetrics | null
}

export interface MessageResponse {
  message: string
}

export interface HealthResponse {
  status: string
  services_running: number
  services_total: number
}
