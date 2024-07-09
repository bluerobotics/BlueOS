import { Platform } from '@/types/autopilot'

export default function toBoardFriendlyChannel(board: string | undefined, servo: string): string {
  const servo_number = parseInt(servo.replace('SERVO', '').replace('_FUNCTION', ''), 10)
  if (board === Platform.Pixhawk1) {
    if (servo_number >= 9) {
      return `Aux ${servo_number - 8}`
    }
  }
  return `Channel ${servo_number}`
}
