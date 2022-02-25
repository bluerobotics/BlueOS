import { JSONValue } from '@/types/common'

export interface MavlinkHeader {
    system_id: number,
    component_id: number,
    sequence: number
}
export interface MavlinkData {
    header: MavlinkHeader,
    message: JSONValue
}

export interface MavlinkMessage {
    messageName: string
    messageData: MavlinkData
    requestedMessageRate: number
    timestamp: Date
}
