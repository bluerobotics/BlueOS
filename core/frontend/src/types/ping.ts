import { Dictionary } from '@/types/common'

export interface PingDevice {
  ping_type: string,
  device_id: number,
  device_model: number,
  device_revision: number,
  firmware_version_major: number,
  firmware_version_minor: number,
  firmware_version_patch: number,
  port: string,
  driver_status: Dictionary<number|boolean|string>
}
