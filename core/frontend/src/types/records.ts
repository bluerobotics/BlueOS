export type RecordingState = 'recording' | 'ready' | 'needs_repair' | 'repairing'

export interface RecordingFile {
  name: string
  path: string
  size_bytes: number
  created: number
  state: RecordingState
  download_url: string
  stream_url: string
}

export interface ProcessingFile {
  name: string
  path: string
}

export interface FailedRepair extends ProcessingFile {
  error: string
}

export interface ProcessingStatus {
  processing: ProcessingFile[]
  failed: FailedRepair[]
}

export interface SplitRecordingResponse {
  recording: RecordingFile
  status: ProcessingStatus
}
