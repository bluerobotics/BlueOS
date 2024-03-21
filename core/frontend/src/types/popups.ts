/**
 * The type of icon to display in the popup
 */
export type PopupIcon = 'info' | 'warning' | 'error' | 'success' | 'question'

/**
 * The priority of the popup, if it should be on top of others
 */
export type PopupPriority = 'low' | 'medium' | 'high'

/**
 * Options used when launching a popup
 * @interface PopupOptions
 */
export interface PopupOptions {
  /**
   * The id of the popup
   * @type {string}
   */
  id?: string

  /**
   * The title of the popup that will appear at the top
   * @type {string}
   */
  title: string

  /**
   * The main text of the popup
   * @type {string}
   */
  text: string

  /**
   * The icon to display in the popup
   * @default undefined
   * @type {PopupIconType}
   */
  icon?: PopupIcon

  /**
   * The priority of the popup, if it should be on top of others
   * @default PopupPriority.Low
   * @type {PopupPriority}
   */
  priority?: PopupPriority

  /**
   * Whether the popup should have a close button as a cross in the top right corner
   * @default true
   * @type {boolean}
   */
  showCloseButton?: boolean

  /**
   * Whether the popup should be dismissible by pressing the escape key
   * @default true
   * @type {boolean}
   */
  allowEscToClose?: boolean

  /**
   * Whether the popup should be dismissible by clicking outside of the popup
   * @default true
   * @type {boolean}
   */
  allowClickToClose?: boolean

  /**
   * Whether the popup should prevent clicking outside of the popup
   * @default false
   * @type {boolean}
   */
  preventClick?: boolean

  /**
   * Whether the popup should have a cancel button
   * @default true
   * @type {boolean}
   */
  showCancelButton?: boolean

  /**
   * Whether the popup should have a confirm button
   * @default true
   * @type {boolean}
   */
  showConfirmButton?: boolean

  /**
   * The text to display on the cancel button
   * @default 'Cancel'
   * @type {string}
   */
  cancelButtonText?: string

  /**
   * The text to display on the confirm button
   * @default 'Confirm'
   * @type {string}
   */
  confirmButtonText?: string
}

/**
 * The result of a popup promise
 * @interface PopupResult
 */
export interface PopupResult {
  /**
   * The id of the popup that was fired
   * @type {string}
   */
  id: string

  /**
   * Whether the popup was dismissed without one of cancel or confirm being clicked
   * @type {boolean}
   */
  dismissed: boolean

  /**
   * Whether the popup was confirmed
   * @type {boolean}
   */
  confirmed: boolean

  /**
   * Whether the popup was canceled
   * @type {boolean}
   */
  canceled: boolean
}

/**
 * The callback to used to resolve a popup promise
 * @callback ResolvePopupCallback
 */
export type ResolvePopupCallback = (value: PopupResult) => void

/**
 * Represents a current open and mounted popup
 * @interface
 */
export interface ActivePopup {
  /**
   * The id of the popup
   * @type {string}
   */
  id: string

  /**
   * Options used in this popup
   * @type {PopupOptions}
   */
  options: PopupOptions

  /**
   * If the popup was dismissed by external call
   * @type {boolean}
   */
  dismissed: boolean

  /**
   * Callback used to resolve this popup
   * @type {ResolvePopupCallback}
   */
  resolve: ResolvePopupCallback
}
