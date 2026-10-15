import {
  AlertRule, AlertRuleId, AlertSource,
} from '@/types/alerts'
import frontend from '@/store/frontend'
import { frontend_service } from '@/types/frontend_services'
import { NotificationLevel } from '@/types/notifications'

const rules: AlertRule[] = [
  {
    id: AlertRuleId.BackendOffline,
    source: AlertSource.Frontend,
    service: frontend_service,
    level: NotificationLevel.Critical,
    title: 'Backend is offline',
    condition: () => frontend.backend_offline,
  },
]


export default rules