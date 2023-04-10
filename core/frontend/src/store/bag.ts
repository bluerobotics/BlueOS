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

  async setData(path: string, payload: Record<string, unknown>): Promise<boolean> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/set/${path}`,
      timeout: 5000,
      data: payload,
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

  async getData(path: string): Promise<Record<string, unknown> | undefined> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/get/${path}`,
      timeout: 5000,
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error === backend_offline_error) {
          return undefined
        }
        const message = `Could not get data: ${error.response?.data ?? error.message}.`
        notifier.pushError('BAG_OF_HOLDERS_GET_DATA_FAIL', message, true)
        return undefined
      })
  }
}

const bag = BagOfHoldersStore.getInstance()
export default bag
