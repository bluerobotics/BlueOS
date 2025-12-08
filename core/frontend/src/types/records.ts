export interface RecordingFile {
  name: string
  path: string
  size_bytes: number
  modified: number
  download_url: string
  stream_url: string
  thumbnail_url: string
}

export interface ProcessingFile {
  name: string
  path: string
}

export interface ProcessingStatus {
  processing: ProcessingFile[]
}
