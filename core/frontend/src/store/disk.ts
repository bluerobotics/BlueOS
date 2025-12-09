import {
  Action, Module, Mutation, VuexModule, getModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { DiskUsageQuery, DiskUsageResponse } from '@/types/disk'
import back_axios, { isBackendOffline } from '@/utils/api'

@Module({ dynamic: true, store, name: 'disk' })
class DiskStore extends VuexModule {
  API_URL = '/disk-usage/v1.0/disk'

  usage: DiskUsageResponse | null = null

  loading = false

  deleting = false

  error: string | null = null

  @Mutation
  setUsage(value: DiskUsageResponse | null): void {
    this.usage = value
  }

  @Mutation
  setLoading(value: boolean): void {
    this.loading = value
  }

  @Mutation
  setDeleting(value: boolean): void {
    this.deleting = value
  }

  @Mutation
  setError(message: string | null): void {
    this.error = message
  }

  @Action
  async fetchUsage(query: DiskUsageQuery): Promise<void> {
    this.setLoading(true)
    this.setError(null)

    await back_axios({
      method: 'get',
      url: `${this.API_URL}/usage`,
      params: query,
      timeout: 120000,
    })
      .then((response) => {
        this.setUsage(response.data as DiskUsageResponse)
      })
      .catch((error) => {
        this.setUsage(null)
        if (isBackendOffline(error)) {
          return
        }
        this.setError(`Failed to fetch disk usage: ${error.message}`)
      })
      .finally(() => {
        this.setLoading(false)
      })
  }

  @Action
  async deletePath(path: string): Promise<void> {
    this.setDeleting(true)
    this.setError(null)
    await back_axios({
      method: 'delete',
      url: `${this.API_URL}/paths/${encodeURIComponent(path)}`,
      timeout: 120000,
    })
      .then(async () => {
        // Refresh after delete using the current usage query to reflect changes
        if (this.usage) {
          await this.fetchUsage({
            path: this.usage.root.path,
            depth: this.usage.depth,
            include_files: this.usage.include_files,
            min_size_bytes: this.usage.min_size_bytes,
          })
        }
      })
      .catch((error) => {
        if (isBackendOffline(error)) {
          return
        }
        this.setError(`Failed to delete path: ${error.response?.data?.detail || error.message}`)
      })
      .finally(() => {
        this.setDeleting(false)
      })
  }
}

const disk_store = getModule(DiskStore)

export { DiskStore }
export default disk_store
