import { SocketKind } from '@/types/common'

export interface NMEASocket {
  kind: SocketKind
  port: number
  component_id: number
}
