import helper from '@/store/helper'
import wifi from '@/store/wifi'
import {
  AlertRule, AlertRuleId, AlertSource,
} from '@/types/alerts'
import { helper_service, wifi_service } from '@/types/frontend_services'
import { InternetConnectionState } from '@/types/helper'
import { ruleSet } from '../define'
import { NotificationLevel } from '@/types/notifications'

const INTERFACES_PENDING_MS = 40000

const defineRules = ruleSet({
  source: AlertSource.Frontend,
  pending_ms: 1000,
  keep_firing_filter_ms: 1000,
  inhibited_by: [AlertRuleId.BackendOffline],
})

const rules: AlertRule[] = defineRules([
  {
    id: AlertRuleId.NetworkDnsFailure,
    service: helper_service,
    level: NotificationLevel.Warning,
    title: 'DNS is not resolving names',
    description: 'The network link is working but domain names cannot be resolved. Check the DNS settings.',
    condition: () => helper.dns_failure,
  },
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
  },
  {
    id: AlertRuleId.NetworkPreferredInterfaceNoInternet,
    service: helper_service,
    level: NotificationLevel.Error,
    title: 'Preferred network interface has no internet',
    description: 'Another interface is online. Check the connection or change the interfaces priority.',
    pending_ms: INTERFACES_PENDING_MS,
    condition: () => helper.has_internet === InternetConnectionState.OFFLINE
      && helper.preferred_interface_has_no_internet,
  },
  {
    id: AlertRuleId.NetworkFasterInterfaceAvailable,
    service: helper_service,
    level: NotificationLevel.Warning,
    title: 'Preferred network interface is slow',
    description: 'Another interface is faster. Check the connection or change the interfaces priority.',
    pending_ms: INTERFACES_PENDING_MS,
    inhibited_by: [AlertRuleId.NetworkPreferredInterfaceNoInternet],
    condition: () => helper.faster_interface_available,
  },
])


export default rules
