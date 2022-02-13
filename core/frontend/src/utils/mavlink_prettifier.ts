import { Dictionary } from '@/types/common'

const formatters = {
  AHRS2(message: any) {
    return `AHRS2 - Roll: ${message.roll.toFixed(2)} rad, Pitch: `
    + `${message.pitch.toFixed(2)} rad, Yaw: ${message.yaw.toFixed(2)} rad`
  },
  ATTITUDE(message: any): string {
    return `ATTITUDE - Roll: ${message.roll.toFixed(2)} rad, Pitch: `
    + `${message.pitch.toFixed(2)} rad, Yaw: ${message.yaw.toFixed(2)} rad`
  },
  BATTERY_STATUS(message: any) {
    return `BATTERY_STATUS - ${message.voltages[0] / 1000} V ${message.current_consumed} mAh consumed`
  },
  COMMAND_ACK(message: any) {
    return `COMMAND_ACK - ${message.command.type.replace('MAV_CMD_', '')}`
      + ` - ${message.result.type.replace('MAV_RESULT_', '')}`
  },
  GLOBAL_POSITION_INT(message: any) {
    return `GLOBAL_POSITION_INT - Lat: ${message.lat.toFixed(5)} Lon: ${message.lon.toFixed(5)}`
  },
  HEARTBEAT(message: any) {
    return `HEATBEAT - ${message.mavtype.type}`
  },
  NAMED_VALUE_FLOAT(message: any) {
    return `NAMED_VALUE_FLOAT - ${message.name.join('')} = ${message.value.toFixed(2)}`
  },
  STATUSTEXT(message: any): string {
    return `${message.severity.type.replace('MAV_SEVERITY_', '')}: ${message.text.join('')}`
  },
  SYS_STATUS(message: any) {
    return `SYS_STATUS - Batt: (${message.current_battery / 100} A, ${message.voltage_battery / 1000} V)`
  },
} as Dictionary<(message: any) => string>

export default function prettify(message: any): string {
  if (message.type === undefined) {
    return 'N/A'
  }
  const message_type = message.type as string
  if (message_type in formatters) {
    return formatters[message_type](message)
  }
  return message.type as string
}
