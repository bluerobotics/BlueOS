import { v4 as uuid } from 'uuid'

import popups from '@/store/popups'
import { PopupOptions, PopupResult } from '@/types/popups'

class Popup {
  /**
   * The id of the popup
   * @type {string}
   */
  public id: string

  /**
   * The options to use when firing this popup
   * @type {PopupOptions}
   */
  public options: PopupOptions

  /**
   * Popup constructor
   * @param {PopupOptions} options Options to use when firing the popup
   */
  constructor(options: PopupOptions, id?: string) {
    this.id = id ?? uuid()
    this.options = {
      ...options,
      id: this.id,
    }
  }

  /**
   * Fire a popup with the given options
   * @param {PopupOptions} options Options to use when firing the popup
   * @param {string} id Optional id to use when firing the popup so it can be
   * programmatically closed after
   * @returns {Promise<PopupResult>} A promise that resolves to the popup result
   */
  public static fire(options: PopupOptions, id?: string): Promise<PopupResult> {
    options.id = id ?? options.id ?? uuid()
    return popups.fire(options)
  }

  /**
   * Close a popup with the given id resolving it to a dismissed result
   * @param {string} id The id of the popup to close
   * @returns {void}
   */
  public static close(id: string): void {
    popups.close(id)
  }

  /**
   * Close all popups resolving them to dismissed results
   * @returns {void}
   */
  public static closeAll(): void {
    popups.closeAll()
  }

  /**
   * Close current popup resolving it to a dismissed result
   * @returns {void}
   */
  public close(): void {
    popups.close(this.id)
  }

  /**
   * Fire current popup
   * @returns {Promise<PopupResult>} A promise that resolves to the popup result
   */
  public fire(): Promise<PopupResult> {
    return popups.fire(this.options)
  }
}

export default Popup
