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

/** Base Notification interface to be used for system-user communication */
export interface NotificationInterface {
  /**
   * @param level - Indicates the nature of the notification. Similar to logging systems.
   * @param service - The service that is pushing this notification
   * @param type - Free string used for notification categorization
   * @param message - What is being communicated
   * @param time_created - UNIX timestamp indicating the time of creation
  * */
  level: NotificationLevel
  service: Service
  type: string
  message: string
  time_created: number
}

/** Base class for frontend notification system. */
export class Notification implements NotificationInterface {
  constructor(
    public readonly level: NotificationLevel,
    public readonly service: Service,
    public readonly type: string,
    public readonly message: string,
    public readonly time_created: number,
  ) {}

  /** Compare if all properties (except time_created) between this and other match */
  similarTo(other: Notification): boolean {
    const { time_created: t_this, ...similar_this } = this // eslint-disable-line @typescript-eslint/no-unused-vars
    const { time_created: t_other, ...similar_other } = other // eslint-disable-line @typescript-eslint/no-unused-vars
    return JSON.stringify(similar_this) === JSON.stringify(similar_other)
  }
}

/** Similar to a standard Notification but auto-populates current UNIX timestamp on time_created */
export class LiveNotification extends Notification {
  constructor(
    public level: NotificationLevel,
    public service: Service,
    public type: string,
    public message: string,
  ) {
    super(level, service, type, message, new Date().getTime())
  }
}

/** Interface to represent the cumulation of notifications, counted */
export interface CumulatedNotification {
  notification: Notification
  count: number
}
