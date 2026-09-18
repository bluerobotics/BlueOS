export type RecordingState = 'recording' | 'ready' | 'needs_repair' | 'repairing'

export interface RecordingFile {
  name: string
  path: string
  size_bytes: number
  created: number
  state: RecordingState
  download_url: string
  stream_url: string
  index_url?: string
}

export interface ProcessingFile {
  name: string
  path: string
  bytes_processed?: number
  total_bytes?: number
  bytes_per_second?: number
}

export interface FailedRepair extends ProcessingFile {
  error: string
}

export interface ProcessingStatus {
  processing: ProcessingFile[]
  failed: FailedRepair[]
}
