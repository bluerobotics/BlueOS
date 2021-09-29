import { Baudrate } from '@/types/common'

export interface Bridge {
  serial_path: string
  baud: Baudrate
  ip: string
  udp_port: number
}
