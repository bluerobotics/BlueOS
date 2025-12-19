export type HealthSeverity = 'info' | 'warn' | 'error' | 'critical'
export type HealthSource = 'system' | 'vehicle' | 'extension' | 'network'
export type HealthEventType = 'problem_detected' | 'problem_resolved' | 'problem_updated'

export interface HealthProblem {
  id: string
  severity: HealthSeverity
  title: string
  details: string
  source: HealthSource
  timestamp: number
  metadata?: Record<string, unknown>
  first_seen_ms?: number
  last_seen_ms?: number
}

export interface HealthEvent extends HealthProblem {
  type: HealthEventType
}

export interface HealthSummary {
  active: HealthProblem[]
  updated_at: number
}

export interface HealthHistory {
  events: HealthEvent[]
}
