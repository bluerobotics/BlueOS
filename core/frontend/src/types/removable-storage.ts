export interface RemovableStorageDevice {
  path: string
  name: string
  label: string | null
  uuid: string | null
  filesystem: string
  size_bytes: number
  mount_point: string | null
  mounted: boolean
  managed: boolean
  read_only: boolean
  writable: boolean
}

export interface RemovableStorageResponse {
  devices: RemovableStorageDevice[]
}
