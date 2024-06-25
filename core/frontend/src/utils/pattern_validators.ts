import { isIP } from 'is-ip'

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
  return isIP(ip)
}

export function isUdpAddress(address: string): boolean {
  try {
    return new URL(address).protocol === 'udp:'
  } catch (error) {
    return false
  }
}

export function isRtspAddress(address: string): boolean {
  try {
    return new URL(address).protocol === 'rtsp:'
  } catch (error) {
    return false
  }
}

export function isRtspVariantAddress(address: string): boolean {
  const allowedVariants = ['rtspu:', 'rtspt:', 'rtsph:']

  try {
    const { protocol } = new URL(address)

    return allowedVariants.includes(protocol)
  } catch (error) {
    return false
  }
}


export function isFilepath(filepath: string): boolean {
  const filepath_pattern = /^(.+)\/([^/]+)$/
  return filepath_pattern.test(filepath)
}

export function isNotEmpty<T>(sizable: Array<T> | string | undefined | null): boolean {
  return !!sizable && sizable.length > 0
}
