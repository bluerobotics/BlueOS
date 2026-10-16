/* eslint-disable max-classes-per-file */

import { Service } from './common'

/** Levels of notifications available to be raised */
export enum NotificationLevel {
  Success = 'success',
  Error = 'error',
  Info = 'info',
  Warning = 'warning',
  Critical = 'critical',
}

export function notificationLevelIcon(level: NotificationLevel): string {
  switch (level) {
    case NotificationLevel.Success: return 'mdi-check-bold'
    case NotificationLevel.Error: return 'mdi-close-circle'
    case NotificationLevel.Info: return 'mdi-information'
    case NotificationLevel.Warning: return 'mdi-alert'
    case NotificationLevel.Critical: return 'mdi-skull'
    default: return 'mdi-help-circle'
  }
}

export function notificationLevelColor(level: NotificationLevel): string {
  switch (level) {
    case NotificationLevel.Success: return 'success'
    case NotificationLevel.Error: return 'error'
    case NotificationLevel.Info: return 'info'
    case NotificationLevel.Warning: return 'warning'
    case NotificationLevel.Critical: return 'critical'
    default: return 'info'
  }
}

/** Base Notification interface to be used for system-user communication */
export interface NotificationInterface {
  /**
   * @param level - Indicates the nature of the notification. Similar to logging systems.
   * @param service - The service that is pushing this notification
   * @param type - Free string used for notification categorization
   * @param message - What is being communicated
   * @param time_created - UNIX timestamp indicating the time of creation
   * @param id - Optional external id
  * */
  level: NotificationLevel
  service: Service
  type: string
  message: string
  time_created: number
  id?: string
}

/** Base class for frontend notification system. */
export class Notification implements NotificationInterface {
  constructor(
    public readonly level: NotificationLevel,
    public readonly service: Service,
    public readonly type: string,
    public readonly message: string,
    public readonly time_created: number,
    public readonly id?: string,
  ) {}

}

/** Similar to a standard Notification but auto-populates current UNIX timestamp on time_created */
export class LiveNotification extends Notification {
  constructor(
    public level: NotificationLevel,
    public service: Service,
    public type: string,
    public message: string,
    public id?: string,
  ) {
    super(level, service, type, message, new Date().getTime(), id)
  }
}


/** Notifications sharing the same service and level */
export interface NotificationGroup {
  service: Service
  level: NotificationLevel
  notifications: Notification[]
}
