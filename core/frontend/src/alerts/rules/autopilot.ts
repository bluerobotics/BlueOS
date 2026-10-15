import ardupilot_sensors from '@/store/ardupilot_sensors'
import autopilot_manager from '@/store/autopilot_manager'
import {
  AlertRule, AlertRuleId, AlertSource,
} from '@/types/alerts'
import { autopilot_service } from '@/types/frontend_services'
import { NotificationLevel } from '@/types/notifications'

import { ruleSet } from '../define'

const defineRules = ruleSet({
  source: AlertSource.Frontend,
  service: autopilot_service,
  pending_ms: 5000,
  keep_firing_filter_ms: 2000,
  inhibited_by: [AlertRuleId.BackendOffline],
})

const rules: AlertRule[] = defineRules([
  {
    id: AlertRuleId.AutopilotNoBoard,
    level: NotificationLevel.Warning,
    title: 'No flight controller detected',
    description: 'The autopilot cannot start until a board is connected.',
    condition: () => !autopilot_manager.current_board,
  },
  {
    id: AlertRuleId.AutopilotFirmwareMissing,
    level: NotificationLevel.Warning,
    title: 'Autopilot firmware is not installed',
    description: 'The connected board is in the bootloader. Install firmware before starting the autopilot.',
    condition: () => autopilot_manager.firmware_info === null,
    inhibited_by: [AlertRuleId.AutopilotNoBoard],
  },
  {
    id: AlertRuleId.AutopilotNotConfigured,
    level: NotificationLevel.Warning,
    title: 'Autopilot is not configured',
    condition: () => !autopilot_manager.current_board,
  },
  {
    id: AlertRuleId.AutopilotSensorsUncalibrated,
    level: NotificationLevel.Warning,
    title: 'Some sensors not calibrated',
    description: 'The vehicle may refuse to arm.',
    condition: () => (!ardupilot_sensors.all_sensors_calibrated),
    inhibited_by: [AlertRuleId.AutopilotNotConfigured],
  }
])


export default rules
