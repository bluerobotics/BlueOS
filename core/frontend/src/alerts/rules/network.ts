import helper from '@/store/helper'
import wifi from '@/store/wifi'
import {
  AlertRule, AlertRuleId, AlertSource,
} from '@/types/alerts'
import { helper_service, wifi_service } from '@/types/frontend_services'
import { InternetConnectionState } from '@/types/helper'
import { ruleSet } from '../define'
import { NotificationLevel } from '@/types/notifications'

const defineRules = ruleSet({
  source: AlertSource.Frontend,
  pending_ms: 1000,
  keep_firing_filter_ms: 1000,
  inhibited_by: [AlertRuleId.BackendOffline],
})

const rules: AlertRule[] = defineRules([
  {
    id: AlertRuleId.NetworkWifiUnavailable,
    service: wifi_service,
    level: NotificationLevel.Warning,
    title: 'WiFi is unavailable',
    description: 'BlueOS cannot reach the WiFi manager. Check the WiFi adapter.',
    condition: () => {
      if (!wifi.network_status || !wifi.saved_networks?.length) {
        return undefined
      }
      return wifi.network_status.state === 'unavailable'
    },
  },
  {
    id: AlertRuleId.NetworkNoInternet,
    service: helper_service,
    level: NotificationLevel.Warning,
    title: 'No internet connection',
    description: 'Some features are unavailable',
    condition: () => 
      helper.has_internet === InternetConnectionState.OFFLINE ||
      helper.has_internet === InternetConnectionState.UNKNOWN,
  }
])


export default rules
