import { Service } from './common'
import { NotificationLevel } from './notifications'

export enum AlertRuleId {
  AutopilotFirmwareMissing = 'autopilot.firmware_missing',
  AutopilotNoBoard = 'autopilot.no_board',
  AutopilotNotConfigured = 'autopilot.not_configured',
  AutopilotSensorsUncalibrated = 'autopilot.sensors_uncalibrated',
  BackendOffline = 'backend.offline',
  NetworkDnsFailure = 'network.dns_failure',
  NetworkFasterInterfaceAvailable = 'network.faster_interface_available',
  NetworkNoInternet = 'network.no_internet',
  NetworkPreferredInterfaceNoInternet = 'network.preferred_interface_no_internet',
  NetworkWifiUnavailable = 'network.wifi_unavailable',
}

export enum AlertLifecycle {
  Pending = 'pending',
  Fired = 'fired',
  TimedOut = 'timed_out',
  Dismissed = 'dismissed',
}

export enum AlertSource {
  Frontend = 'frontend',
  Backend = 'backend',
}

export interface AlertRule {
  id: AlertRuleId
  source: AlertSource
  service: Service
  level: NotificationLevel
  title: string
  description?: string
  condition: () => boolean | undefined
  inhibited_by?: AlertRuleId[]
  /** How long the alert stays fired after the condition clears */
  keep_firing_filter_ms?: number
  /** How long the condition must stay true before the alert fires */
  pending_ms?: number
  /** How long the alert stays fired before it is automatically cleared */
  timeout_ms?: number
}

export interface Alert {
  rule_id: AlertRuleId,
  state: AlertLifecycle,
  since: Date,
}
