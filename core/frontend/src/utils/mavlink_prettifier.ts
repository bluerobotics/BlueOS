import { Message } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest'
import { Message as M2R } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-message'
import { Dictionary } from '@/types/common'

const formatters = {
  AHRS2(message: M2R.Ahrs2) {
    return `Roll: ${message.roll.toFixed(2)} rad, Pitch: `
    + `${message.pitch.toFixed(2)} rad, Yaw: ${message.yaw.toFixed(2)} rad`
  },
  ATTITUDE(message: M2R.Attitude): string {
    return `Roll: ${message.roll.toFixed(2)} rad, Pitch: `
    + `${message.pitch.toFixed(2)} rad, Yaw: ${message.yaw.toFixed(2)} rad`
  },
  BATTERY_STATUS(message: M2R.BatteryStatus) {
    return `${message.voltages[0] / 1000} V ${message.current_consumed} mAh consumed`
  },
  CAMERA_INFORMATION(message: M2R.CameraInformation) {
    function byteArrayToString(array: number[]): string {
      return array
        .filter((value: number) => value !== 0)
        .map((value: number) => String.fromCharCode(value))
        .join('')
    }
    function removeNullFromCharArray(array: string[]): string {
      return array
        .filter((value) => value !== '\x00')
        .join('')
    }
    const vendor_name = byteArrayToString(message.vendor_name)
    const definition_url = removeNullFromCharArray(message.cam_definition_uri)
    return `vendor: ${vendor_name}, definition_url: ${definition_url}`
  },
  COMMAND_ACK(message: M2R.CommandAck) {
    return `${message.command.type.replace('MAV_CMD_', '')}`
      + ` - ${message.result.type.replace('MAV_RESULT_', '')}`
  },
  COMMAND_LONG(message: M2R.CommandLong) {
    function getParameters(): string {
      return Object.getOwnPropertyNames(message)
        .filter((name) => name.includes('param'))
        .map((name) => `${name}: ${message[name]}`)
        .join(', ')
    }
    return `${message.command.type.replace('MAV_CMD_', '')}`
      + ` - ${getParameters()}`
  },
  GLOBAL_POSITION_INT(message: M2R.GlobalPositionInt) {
    return `Lat: ${message.lat.toFixed(5)} Lon: ${message.lon.toFixed(5)}`
  },
  HEARTBEAT(message: M2R.Heartbeat) {
    return `${message.mavtype.type}`
  },
  NAMED_VALUE_FLOAT(message: M2R.NamedValueFloat) {
    return `${message.name.join('')} = ${message.value.toFixed(2)}`
  },
  PARAM_VALUE(message: M2R.ParamValue) {
    return `${message.param_id.join('')}: ${message.param_value}`
  },
  SCALED_PRESSURE(message: M2R.ScaledPressure) {
    return `${message.press_abs?.toFixed(2)}hPa at ${message.temperature / 100}c`
  },
  STATUSTEXT(message: M2R.Statustext): string {
    return `${message.severity.type.replace('MAV_SEVERITY_', '')}: ${message.text.join('')}`
  },
  SYS_STATUS(message: M2R.SysStatus) {
    return `Batt: (${message.current_battery / 100} A, ${message.voltage_battery / 1000} V)`
  },
} as Dictionary<(message: unknown) => string>

export default function prettify(message: Message): string {
  if (message.type === undefined) {
    return 'N/A'
  }
  const message_type = message.type as string
  if (message_type in formatters) {
    return `${message_type} - ${formatters[message_type](message)}`
  }

  // There is no function that matches exactly the message
  // Lets check if it's an enumeration of it
  const function_name = Object.keys(formatters).filter((key) => new RegExp(`^${key}\\d+$`).test(message_type))?.first()
  if (function_name) {
    return `${message_type} - ${formatters[function_name](message)}`
  }

  return message_type
}
