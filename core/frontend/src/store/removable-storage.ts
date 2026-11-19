import {
  Action, getModule,
  Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import store from '@/store'
import { removable_storage_service } from '@/types/frontend_services'
import { RemovableStorageDevice, RemovableStorageResponse } from '@/types/removable-storage'
import back_axios, { isBackendOffline } from '@/utils/api'
import { DynamicModule as Module } from '@/utils/vuex'

const API_URL = '/removable-storage/v1.0'
const notifier = new Notifier(removable_storage_service)

@Module({ dynamic: true, store, name: 'removable-storage' })
class RemovableStorageStore extends VuexModule {
  devices: RemovableStorageDevice[] = []

  loading = false

  error: string | null = null

  operatingPaths: string[] = []

  @Mutation
  setDevices(devices: RemovableStorageDevice[]): void {
    this.devices = devices
  }

  @Mutation
  setStorageLoading(loading: boolean): void {
    this.loading = loading
  }

  @Mutation
  setStorageError(error: string | null): void {
    this.error = error
  }

  @Mutation
  setOperating({ path, operating }: { path: string; operating: boolean }): void {
    this.operatingPaths = operating
      ? [...this.operatingPaths, path]
      : this.operatingPaths.filter((operatingPath) => operatingPath !== path)
  }

  @Action
  async fetchStorageDevices(): Promise<void> {
    this.setStorageLoading(this.devices.length === 0)
    try {
      const response = await back_axios({ method: 'get', url: `${API_URL}/devices`, timeout: 10000 })
      this.setDevices((response.data as RemovableStorageResponse).devices)
      this.setStorageError(null)
    } catch (error: unknown) {
      if (!isBackendOffline(error)) {
        const axiosError = error as { response?: { data?: { detail?: string } }; message?: string }
        this.setStorageError(
          axiosError.response?.data?.detail || axiosError.message || 'Failed to fetch USB storage devices.',
        )
      }
    } finally {
      this.setStorageLoading(false)
    }
  }

  @Action
  async mountDevice(device: RemovableStorageDevice): Promise<void> {
    this.setOperating({ path: device.path, operating: true })
    try {
      await back_axios({
        method: 'post',
        url: `${API_URL}/devices/mount`,
        data: { path: device.path },
        timeout: 30000,
      })
      notifier.pushSuccess('USB_MOUNT_SUCCESS', `${device.label || device.path} mounted.`, true)
    } catch (error: unknown) {
      notifier.pushBackError('USB_MOUNT_FAIL', error, true)
    } finally {
      await this.fetchStorageDevices()
      this.setOperating({ path: device.path, operating: false })
    }
  }

  @Action
  async unmountDevice(device: RemovableStorageDevice): Promise<void> {
    this.setOperating({ path: device.path, operating: true })
    try {
      await back_axios({
        method: 'post',
        url: `${API_URL}/devices/unmount`,
        data: { path: device.path },
        timeout: 30000,
      })
      notifier.pushSuccess('USB_UNMOUNT_SUCCESS', `${device.label || device.path} unmounted.`, true)
    } catch (error: unknown) {
      notifier.pushBackError('USB_UNMOUNT_FAIL', error, true)
    } finally {
      await this.fetchStorageDevices()
      this.setOperating({ path: device.path, operating: false })
    }
  }
}

const removable_storage_store = getModule(RemovableStorageStore)

export { RemovableStorageStore }
export default removable_storage_store
