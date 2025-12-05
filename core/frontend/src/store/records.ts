import {
  Action, Module, Mutation, VuexModule, getModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { RecordingFile } from '@/types/records'
import back_axios, { isBackendOffline } from '@/utils/api'

@Module({ dynamic: true, store, name: 'records' })
class RecordsStore extends VuexModule {
  API_URL = '/recorder-extractor/v1.0/recorder'

  recordings: RecordingFile[] = []

  loading = false

  error: string | null = null

  @Mutation
  setLoading(value: boolean): void {
    this.loading = value
  }

  @Mutation
  setRecordings(files: RecordingFile[]): void {
    this.recordings = files
  }

  @Mutation
  setError(message: string | null): void {
    this.error = message
  }

  @Action
  async fetchRecordings(): Promise<void> {
    this.setLoading(true)
    this.setError(null)
    await back_axios({
      method: 'get',
      url: `${this.API_URL}/files`,
      timeout: 10000,
    })
      .then((response) => {
        this.setRecordings(response.data)
      })
      .catch((error) => {
        this.setRecordings([])
        if (isBackendOffline(error)) {
          return
        }
        this.setError(`Failed to fetch recordings: ${error.message}`)
      })
      .finally(() => {
        this.setLoading(false)
      })
  }

  @Action
  async deleteRecording(file: RecordingFile): Promise<void> {
    await back_axios({
      method: 'delete',
      url: `${this.API_URL}/files/${file.path}`,
      timeout: 10000,
    }).catch((error) => {
      if (isBackendOffline(error)) {
        return
      }
      this.setError(`Failed to delete recording: ${error.message}`)
    })
    await this.fetchRecordings()
  }
}

const records_store = getModule(RecordsStore)

export { RecordsStore }
export default records_store
