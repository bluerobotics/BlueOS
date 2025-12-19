import {
  Action, Module, Mutation, VuexModule, getModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { HealthHistory, HealthSummary } from '@/types/health-monitor'
import back_axios, { isBackendOffline } from '@/utils/api'

@Module({ dynamic: true, store, name: 'health_monitor' })
class HealthMonitorStore extends VuexModule {
  API_URL = '/health-monitor/v1.0/health'

  summary: HealthSummary | null = null

  history: HealthHistory | null = null

  loading = false

  error: string | null = null

  @Mutation
  setSummary(value: HealthSummary | null): void {
    this.summary = value
  }

  @Mutation
  setHistory(value: HealthHistory | null): void {
    this.history = value
  }

  @Mutation
  setLoading(value: boolean): void {
    this.loading = value
  }

  @Mutation
  setError(message: string | null): void {
    this.error = message
  }

  @Action
  async fetchSummary(): Promise<void> {
    this.setLoading(true)
    this.setError(null)

    await back_axios({
      method: 'get',
      url: `${this.API_URL}/summary`,
      timeout: 10000,
    })
      .then((response) => {
        this.setSummary(response.data as HealthSummary)
      })
      .catch((error) => {
        this.setSummary(null)
        if (isBackendOffline(error)) {
          return
        }
        this.setError(`Failed to fetch health summary: ${error.message}`)
      })
      .finally(() => {
        this.setLoading(false)
      })
  }

  @Action
  async fetchHistory(limit = 200): Promise<void> {
    await back_axios({
      method: 'get',
      url: `${this.API_URL}/history`,
      params: { limit },
      timeout: 10000,
    })
      .then((response) => {
        this.setHistory(response.data as HealthHistory)
      })
      .catch((error) => {
        this.setHistory(null)
        if (isBackendOffline(error)) {
          return
        }
        this.setError(`Failed to fetch health history: ${error.message}`)
      })
  }
}

const health_monitor = getModule(HealthMonitorStore)

export { HealthMonitorStore }
export default health_monitor
