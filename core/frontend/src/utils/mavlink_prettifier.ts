import { Dictionary } from '@/types/common'

const formatters = {
  AHRS2(message: any) {
    return `Roll: ${message.roll.toFixed(2)} rad, Pitch: `
    + `${message.pitch.toFixed(2)} rad, Yaw: ${message.yaw.toFixed(2)} rad`
  },
  ATTITUDE(message: any): string {
    return `Roll: ${message.roll.toFixed(2)} rad, Pitch: `
    + `${message.pitch.toFixed(2)} rad, Yaw: ${message.yaw.toFixed(2)} rad`
  },
  BATTERY_STATUS(message: any) {
    return `${message.voltages[0] / 1000} V ${message.current_consumed} mAh consumed`
  },
  COMMAND_ACK(message: any) {
    return `${message.command.type.replace('MAV_CMD_', '')}`
      + ` - ${message.result.type.replace('MAV_RESULT_', '')}`
  },
  GLOBAL_POSITION_INT(message: any) {
    return `Lat: ${message.lat.toFixed(5)} Lon: ${message.lon.toFixed(5)}`
  },
  HEARTBEAT(message: any) {
    return `${message.mavtype.type}`
  },
  NAMED_VALUE_FLOAT(message: any) {
    return `${message.name.join('')} = ${message.value.toFixed(2)}`
  },
  STATUSTEXT(message: any): string {
    return `${message.severity.type.replace('MAV_SEVERITY_', '')}: ${message.text.join('')}`
  },
  SYS_STATUS(message: any) {
    return `Batt: (${message.current_battery / 100} A, ${message.voltage_battery / 1000} V)`
  },
} as Dictionary<(message: any) => string>

export default function prettify(message: any): string {
  if (message.type === undefined) {
    return 'N/A'
  }
  const message_type = message.type as string
  if (message_type in formatters) {
    return `${message_type} - ${formatters[message_type](message)}`
  }
  return message_type
}
