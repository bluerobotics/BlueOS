import { StatusCodes } from 'http-status-codes'

import Notifier from '@/libs/notifier'
import { bag_of_holders_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'

const notifier = new Notifier(bag_of_holders_service)

class BagOfHoldersStore {
  API_URL = '/bag/v1.0'

  private static instance: BagOfHoldersStore

  public static getInstance(): BagOfHoldersStore {
    if (!BagOfHoldersStore.instance) {
      BagOfHoldersStore.instance = new BagOfHoldersStore()
    }
    return BagOfHoldersStore.instance
  }

  async overwrite(payload: Record<string, unknown>): Promise<boolean> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/overwrite`,
      timeout: 5000,
      data: payload,
    })
      .then(() => true)
      .catch((error) => {
        if (error === backend_offline_error) {
          return false
        }
        const message = `Could not overwrite database: ${error.message ?? error.response?.data}.`
        notifier.pushError('BAG_OF_HOLDERS_SET_DATA_FAIL', message, true)
        return false
      })
  }

  async setData(path: string, payload: Record<string, unknown> | undefined = undefined): Promise<boolean> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/set/${path}`,
      timeout: 5000,
      data: payload ?? {},
    })
      .then(() => true)
      .catch((error) => {
        if (error === backend_offline_error) {
          return false
        }
        const message = `Could not set data: ${error.message ?? error.response?.data}.`
        notifier.pushError('BAG_OF_HOLDERS_SET_DATA_FAIL', message, true)
        return false
      })
  }

  /**
   * null is used when the bath don't exist on the system
   * undefined is returned when there is no communication with backend
   */
  async getData(path: string): Promise<Record<string, unknown> | null | undefined> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/get/${path}`,
      timeout: 5000,
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error?.response?.status === StatusCodes.BAD_REQUEST) {
          return null
        }

        if (error === backend_offline_error) {
          return undefined
        }
        const message = `Could not get (${path}) data: ${error.response?.data ?? error.message}.`
        notifier.pushError('BAG_OF_HOLDERS_GET_DATA_FAIL', message, true)
        return undefined
      })
  }
}

const bag = BagOfHoldersStore.getInstance()
export default bag
