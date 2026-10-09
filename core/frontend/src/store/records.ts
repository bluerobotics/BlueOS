import {
  Action, getModule,
  Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import {
  FailedRepair, ProcessingFile, RecordingFile,
} from '@/types/records'
import back_axios, { isBackendOffline } from '@/utils/api'
import { DynamicModule as Module } from '@/utils/vuex'

@Module({ dynamic: true, store, name: 'records' })
class RecordsStore extends VuexModule {
  API_URL = '/recorder-extractor/v1.0'

  recordings: RecordingFile[] = []

  processing_files: ProcessingFile[] = []

  failed_repairs: FailedRepair[] = []

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
  setProcessingFiles(files: ProcessingFile[]): void {
    this.processing_files = files
  }

  @Mutation
  setFailedRepairs(failures: FailedRepair[]): void {
    this.failed_repairs = failures
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

  @Action
  async fetchProcessingStatus(): Promise<void> {
    await back_axios({
      method: 'get',
      url: `${this.API_URL}/status`,
      timeout: 10000,
    })
      .then((response) => {
        this.setProcessingFiles(response.data.processing)
        this.setFailedRepairs(response.data.failed ?? [])
      })
      .catch((error) => {
        if (isBackendOffline(error)) {
          return
        }
        this.setProcessingFiles([])
      })
  }

  /**
   * Asks the vehicle to rewrite a recording so that it carries an index again. The rewrite runs on
   * the vehicle and is followed through the processing status, since it takes as long as copying the
   * recording.
   */
  @Action
  async repairRecording(file: RecordingFile): Promise<void> {
    await back_axios({
      method: 'post',
      url: `${this.API_URL}/files/${file.path}/repair`,
      timeout: 10000,
    })
      .then((response) => {
        this.setProcessingFiles(response.data.processing)
        this.setFailedRepairs(response.data.failed ?? [])
      })
      .catch((error) => {
        if (isBackendOffline(error)) {
          return
        }
        const detail = error.response?.data?.detail
        this.setError(`Could not repair ${file.name}: ${detail ?? error.message}`)
      })
  }

  /** Stops a running rewrite. The recording is left exactly as it was, so it can be repaired again. */
  @Action
  async cancelRepair(file: RecordingFile): Promise<void> {
    await back_axios({
      method: 'delete',
      url: `${this.API_URL}/files/${file.path}/repair`,
      timeout: 10000,
    })
      .then((response) => {
        this.setProcessingFiles(response.data.processing)
      })
      .catch((error) => {
        if (isBackendOffline(error)) {
          return
        }
        const detail = error.response?.data?.detail
        this.setError(`Could not stop repairing ${file.name}: ${detail ?? error.message}`)
      })
  }
}

const records_store = getModule(RecordsStore)

export { RecordsStore }
export default records_store
