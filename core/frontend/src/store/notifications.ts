import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { Notification, NotificationLevel } from '@/types/notifications'

@Module({
  dynamic: true,
  store,
  name: 'notifications',
})

@Module
class NotificationsStore extends VuexModule {
  notifications: Notification[] = []

  dismissed_notifications: Notification[] = []

  @Mutation
  pushNotification(notification: Notification): void {
    this.notifications.push(notification)

    switch (notification.level) {
      case NotificationLevel.Success:
        console.log(notification.message)
        break
      case NotificationLevel.Error:
        console.error(notification.message)
        break
      case NotificationLevel.Info:
        console.info(notification.message)
        break
      case NotificationLevel.Warning:
        console.warn(notification.message)
        break
      case NotificationLevel.Critical:
        console.error(notification.message)
        break
      default:
        console.warn(`A new notification level was added but we have not updated
        this part of the code. Regardless of that, here's the notification message: ${notification.message}`)
        break
    }
  }

  @Mutation
  dismissNotification(notification: Notification): void {
    this.dismissed_notifications.push(notification)
  }

  get active_notifications(): Notification[] {
    return this.notifications.filter(
      (notification) => !this.dismissed_notifications.includes(notification),
    )
  }
}

export { NotificationsStore }

const notifications: NotificationsStore = getModule(NotificationsStore)
export default notifications
