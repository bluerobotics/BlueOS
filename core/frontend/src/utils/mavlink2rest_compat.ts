import { MavModeFlag } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'

type MavlinkString = string | readonly (number | string)[] | null | undefined
type MavlinkFlags = string | { bits: number } | null | undefined

export function mavlinkString(value: MavlinkString): string {
  if (typeof value === 'string') return value.replace(/\0/g, '')
  if (!value) return ''
  return value
    .map((character) => {
      if (typeof character === 'number') return String.fromCharCode(character)
      return character
    })
    .join('')
    .replace(/\0/g, '')
}

export function mavlinkFlagEnabled(
  value: MavlinkFlags,
  flagName: keyof typeof MavModeFlag,
  flagValue: MavModeFlag,
): boolean {
  if (typeof value === 'string') {
    return value.split('|').some((flag) => flag.trim() === flagName)
  }
  if (!value) return false
  return Boolean(value.bits & flagValue)
}
