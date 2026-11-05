import {
  Action, Module, Mutation, VuexModule, getModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { DiskSpeedResult, DiskSpeedTestPoint, DiskUsageQuery, DiskUsageResponse } from '@/types/disk'
import back_axios, { isBackendOffline } from '@/utils/api'
import { parseStreamingResponse } from '@/utils/streaming'

@Module({ dynamic: true, store, name: 'disk' })
class DiskStore extends VuexModule {
  API_URL = '/disk-usage/v1.0/disk'

  usage: DiskUsageResponse | null = null

  loading = false

  deleting = false

  error: string | null = null

  speedResult: DiskSpeedResult | null = null

  speedResults: DiskSpeedTestPoint[] = []

  speedTesting = false

  speedTestProgress = ''

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
  setSpeedResults(value: DiskSpeedTestPoint[]): void {
    this.speedResults = value
  }

  @Mutation
  addSpeedResult(point: DiskSpeedTestPoint): void {
    this.speedResults = [...this.speedResults, point]
  }

  @Mutation
  setSpeedTesting(value: boolean): void {
    this.speedTesting = value
  }

  @Mutation
  setSpeedTestProgress(value: string): void {
    this.speedTestProgress = value
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

  @Action
  async runMultiSizeSpeedTest(): Promise<void> {
    this.setSpeedTesting(true)
    this.setSpeedError(null)
    this.setSpeedResults([])
    this.setSpeedTestProgress('Starting tests...')

    let processedFragments = 0

    try {
      await back_axios({
        method: 'get',
        url: `${this.API_URL}/speed/stream`,
        timeout: 600000,
        onDownloadProgress: (progressEvent: { event?: { currentTarget?: { response?: string } } }) => {
          const response = progressEvent.event?.currentTarget?.response
          if (!response) return

          const fragments = parseStreamingResponse(response)
          const validFragments = fragments.filter((f) => f.fragment >= 0 && f.status === 200 && f.data)

          for (let i = processedFragments; i < validFragments.length; i++) {
            const fragment = validFragments[i]
            if (!fragment.data) continue

            try {
              const point = JSON.parse(fragment.data) as DiskSpeedTestPoint
              this.addSpeedResult(point)
              this.setSpeedTestProgress(`Tested ${point.size_mb} MB`)
            } catch (e) {
              console.error('Failed to parse speed test point:', e)
            }
          }
          processedFragments = validFragments.length
        },
      })

      this.setSpeedTestProgress('Test complete')
    } catch (error) {
      if (isBackendOffline(error)) {
        this.setSpeedTesting(false)
        return
      }
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string }
      const message = axiosError.response?.data?.detail || axiosError.message || 'Unknown error'
      this.setSpeedError(`Speed test failed: ${message}`)
    } finally {
      this.setSpeedTesting(false)
    }
  }
}

const disk_store = getModule(DiskStore)

export { DiskStore }
export default disk_store
