export interface UsbDevice {
  vid: number
  pid: number
  serial_number: string | null
  manufacturer: string | null
  product: string | null
  port_path: string
  bus_number: number
  device_address: number
  device_class: number
  device_subclass: number
  device_protocol: number
  usb_version: string
  speed: string
  num_configurations: number
}

export interface UsbDevicesResponse {
  devices: UsbDevice[]
}

export interface UsbTreeNode {
  device: UsbDevice
  children: UsbTreeNode[]
  depth: number
  portNumber: number | null
}
