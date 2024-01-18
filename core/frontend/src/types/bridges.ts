import { Baudrate } from '@/types/common'
import { SerialPortInfo } from '@/types/system-information/serial'

export interface Bridge {
  serial_path: string
  baud: Baudrate
  ip: string
  udp_listen_port: number
  udp_target_port: number
}

export interface BridgeWithSerialInfo {
  bridge: Bridge
  serial_info: SerialPortInfo | undefined
}
