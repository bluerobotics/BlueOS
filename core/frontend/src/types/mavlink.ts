export interface MavlinkMessage {
    messageName: string
    messageData: {[key: string]: {value: string|number}}
    requestedMessageRate: number
}
