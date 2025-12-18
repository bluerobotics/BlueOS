export interface FileSyncEntry {
  path: string
  size: number
}

export interface UploadingTransfer {
  file: string
  display_path: string
  sent: number
  total: number
  timestamp: number
  progress: number
  completed: boolean
}

export type CloudSyncItemStatus = 'uploading' | 'pending' | 'completed'

export interface CloudSyncDisplayItem {
  id: string
  path: string
  size: number
  status: CloudSyncItemStatus
  display_path?: string
  sent?: number
  total?: number
  progress?: number
}

export interface FileSyncUploadingEvent {
  file?: unknown
  sent?: unknown
  total?: unknown
  timestamp?: unknown
}
