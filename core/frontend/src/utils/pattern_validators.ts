import { Baudrate } from '@/types/common'

export function isSocketPort(port: number, public_range = true): boolean {
  if (!Number.isInteger(port)) {
    return false
  }
  if (port > 65535) {
    return false
  }
  if (public_range) {
    return port >= 1024
  }
  return port >= 0
}

export function isIntegerString(input: string): boolean {
  return input.match(/^[0-9]+$/) != null
}

export function isBaudrate(baudrate: number): boolean {
  return Object.values(Baudrate).map((baud) => parseInt(baud, 10)).includes(baudrate)
}

export function isIpAddress(ip: string): boolean {
  const ip_pattern = /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/
  return ip_pattern.test(ip)
}

export function isUdpAddress(url: string): boolean {
  return url.match(/udp:\/\/[a-zA-Z0-9@:%._+~#=]{2,256}:[0-9]{1,6}/) !== null
}

export function isFilepath(filepath: string): boolean {
  const filepath_pattern = /^(.+)\/([^/]+)$/
  return filepath_pattern.test(filepath)
}

export function isNotEmpty<T>(sizable: Array<T> | string | undefined | null): boolean {
  return !!sizable && sizable.length > 0
}
