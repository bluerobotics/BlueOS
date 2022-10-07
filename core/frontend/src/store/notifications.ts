import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import {
  CumulatedNotification, Notification, NotificationLevel,
} from '@/types/notifications'

@Module({
  dynamic: true,
  store,
  name: 'notifications',
})

@Module
class NotificationsStore extends VuexModule {
  notifications: Notification[] = []

  cumulated_notifications: CumulatedNotification[] = []

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

    // If current notification is similar to the last one, cumulate it on the counter
    const [last_item] = this.cumulated_notifications.slice(-1)
    if (last_item
      && notification.similarTo(last_item.notification)
      && !this.dismissed_notifications.includes(last_item.notification)) {
      last_item.notification = notification
      last_item.count += 1
      return
    }
    this.cumulated_notifications.push({ notification, count: 1 })
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

  get active_cumulated_notifications(): CumulatedNotification[] {
    return this.cumulated_notifications.filter(
      (cumulated) => !this.dismissed_notifications.includes(cumulated.notification),
    )
  }
}

export { NotificationsStore }

const notifications: NotificationsStore = getModule(NotificationsStore)
export default notifications
