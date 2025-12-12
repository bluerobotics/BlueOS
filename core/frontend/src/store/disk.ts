import {
  Action, Module, Mutation, VuexModule, getModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { DiskSpeedResult, DiskUsageQuery, DiskUsageResponse } from '@/types/disk'
import back_axios, { isBackendOffline } from '@/utils/api'

@Module({ dynamic: true, store, name: 'disk' })
class DiskStore extends VuexModule {
  API_URL = '/disk-usage/v1.0/disk'

  usage: DiskUsageResponse | null = null

  loading = false

  deleting = false

  error: string | null = null

  speedResult: DiskSpeedResult | null = null

  speedTesting = false

  speedError: string | null = null

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

  @Mutation
  setSpeedResult(value: DiskSpeedResult | null): void {
    this.speedResult = value
  }

  @Mutation
  setSpeedTesting(value: boolean): void {
    this.speedTesting = value
  }

  @Mutation
  setSpeedError(message: string | null): void {
    this.speedError = message
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
  async deletePaths(paths: string[]): Promise<{ succeeded: string[]; failed: { path: string; error: string }[] }> {
    this.setDeleting(true)
    this.setError(null)

    const deleteOne = async (path: string): Promise<void> => {
      try {
        await back_axios({
          method: 'delete',
          url: `${this.API_URL}/paths/${encodeURIComponent(path)}`,
          timeout: 120000,
        })
      } catch (error: unknown) {
        if (isBackendOffline(error)) {
          throw new Error('Backend is offline')
        }
        const axiosError = error as { response?: { data?: { detail?: string } }; message?: string }
        const message = axiosError.response?.data?.detail || axiosError.message || 'Unknown error'
        throw new Error(message)
      }
    }

    const results = await Promise.allSettled(paths.map((path) => deleteOne(path)))

    const succeeded: string[] = []
    const failed: { path: string; error: string }[] = []

    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        succeeded.push(paths[index])
      } else {
        failed.push({ path: paths[index], error: result.reason?.message || 'Unknown error' })
      }
    })

    if (failed.length > 0) {
      const errorMsg = failed.length === 1
        ? `Failed to delete ${failed[0].path}: ${failed[0].error}`
        : `Failed to delete ${failed.length} path(s): ${failed.map((f) => f.path).join(', ')}`
      this.setError(errorMsg)
    }

    this.setDeleting(false)
    return { succeeded, failed }
  }

  @Action
  async runSpeedTest(sizeBytes: number): Promise<void> {
    this.setSpeedTesting(true)
    this.setSpeedError(null)
    this.setSpeedResult(null)

    await back_axios({
      method: 'get',
      url: `${this.API_URL}/speed`,
      params: { size_bytes: sizeBytes },
      timeout: 600000,
    })
      .then((response) => {
        this.setSpeedResult(response.data as DiskSpeedResult)
      })
      .catch((error) => {
        if (isBackendOffline(error)) {
          return
        }
        const axiosError = error as { response?: { data?: { detail?: string } }; message?: string }
        const message = axiosError.response?.data?.detail || axiosError.message || 'Unknown error'
        this.setSpeedError(`Speed test failed: ${message}`)
      })
      .finally(() => {
        this.setSpeedTesting(false)
      })
  }
}

const disk_store = getModule(DiskStore)

export { DiskStore }
export default disk_store
