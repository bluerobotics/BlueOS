export enum PingType {
  Ping1D = 'Ping1D',
  Ping360 = 'Ping360'
}

export interface DriverStatus {
  udp_port: number | undefined
  mavlink_driver_enabled: boolean
}

export interface PingDevice {
  ping_type: PingType,
  device_id: number,
  device_model: number,
  device_revision: number,
  firmware_version_major: number,
  firmware_version_minor: number,
  firmware_version_patch: number,
  port: string,
  driver_status: DriverStatus,
  ethernet_discovery_info: string
}

export function formatVersion(device: PingDevice): string {
  return `${device.firmware_version_major}.${device.firmware_version_minor}.${device.firmware_version_patch}`
}
