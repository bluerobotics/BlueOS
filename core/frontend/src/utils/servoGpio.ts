/**
 * Maps a 1-based servo channel number to the corresponding GPIO number for ArduPilot.
 * Navigator boards use 1:1; most others follow Pixhawk1 (main 1–8 → 101–108, aux 9–16 → 50–57).
 */
export function servoNumberToGpio(servoNumber: number, boardName: string | undefined): number {
  if (boardName?.startsWith('Navigator')) {
    return servoNumber
  }
  if (servoNumber <= 8) {
    return servoNumber + 100
  }
  return servoNumber - 9 + 50
}
