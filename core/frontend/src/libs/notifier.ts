import notifications from '@/store/notifications'
import { Service } from '@/types/common'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { backend_offline_error } from '@/utils/api'

class Notifier {
  constructor(
      public service: Service,
  ) {}

  push(level: NotificationLevel, type: string, message: string) : void {
    notifications.pushNotification(new LiveNotification(level, this.service, type, message))
  }

  pushSuccess(type: string, message: string): void {
    notifications.pushNotification(new LiveNotification(NotificationLevel.Success, this.service, type, message))
  }

  pushError(type: string, message: string): void {
    notifications.pushNotification(new LiveNotification(NotificationLevel.Error, this.service, type, message))
  }

  pushInfo(type: string, message: string): void {
    notifications.pushNotification(new LiveNotification(NotificationLevel.Info, this.service, type, message))
  }

  pushWarning(type: string, message: string): void {
    notifications.pushNotification(new LiveNotification(NotificationLevel.Warning, this.service, type, message))
  }

  pushCritical(type: string, message: string): void {
    notifications.pushNotification(new LiveNotification(NotificationLevel.Critical, this.service, type, message))
  }

  pushBackError(type: string, error: any): void {
    if (error === backend_offline_error) { return }
    const message = error.response?.data?.detail ?? error.message
    this.pushError(type, message)
  }
}

export default Notifier
