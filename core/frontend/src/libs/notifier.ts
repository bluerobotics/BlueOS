import message_manager, { MessageLevel } from '@/libs/error-message'
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

  pushSuccess(type: string, message: string, alert = false): void {
    if (alert) { message_manager.emitMessage(MessageLevel.Success, message) }
    this.push(NotificationLevel.Success, type, message)
  }

  pushError(type: string, message: string, alert = false): void {
    if (alert) { message_manager.emitMessage(MessageLevel.Error, message) }
    this.push(NotificationLevel.Error, type, message)
  }

  pushInfo(type: string, message: string, alert = false): void {
    if (alert) { message_manager.emitMessage(MessageLevel.Info, message) }
    this.push(NotificationLevel.Info, type, message)
  }

  pushWarning(type: string, message: string, alert = false): void {
    if (alert) { message_manager.emitMessage(MessageLevel.Warning, message) }
    this.push(NotificationLevel.Warning, type, message)
  }

  pushCritical(type: string, message: string, alert = false): void {
    if (alert) { message_manager.emitMessage(MessageLevel.Critical, message) }
    this.push(NotificationLevel.Critical, type, message)
  }

  pushBackError(type: string, error: any, alert = false): void {
    if (error === backend_offline_error) { return }
    const message = error.response?.data?.detail ?? error.message
    this.pushError(type, message, alert)
  }
}

export default Notifier
