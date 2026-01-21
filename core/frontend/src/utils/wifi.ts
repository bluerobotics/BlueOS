import { Network } from '@/types/wifi'

export function wifi_strenght_icon(signal: number): string {
  /*eslint-disable */
  // Signal can be in two formats:
  // 1. Percentage (0-100) from NetworkManager
  // 2. dBm (negative values like -30 to -90) from wpa_supplicant
  //
  // | Signal Strength | TL;DR     |  Description                                                                                                                               |
  // |-----------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------|
  // | -30 dBm / 100%  | Amazing   | Max achievable signal strength. The client can only be a few feet from the AP to achieve this. Not typical or desirable in the real world. |
  // | -67 dBm / 75%   | Very Good | Minimum signal strength for applications that require very reliable, timely delivery of data packets.                                      |
  // | -70 dBm / 50%   | Okay      | Minimum signal strength for reliable packet delivery.                                                                                      |
  // | -80 dBm / 25%   | Not Good  | Minimum signal strength for basic connectivity. Packet delivery may be unreliable.                                                         |
  // | -90 dBm / 0%    | Unusable  | Approaching or drowning in the noise floor. Any functionality is highly unlikely.                                                           |
  // Reference: metageek.com/training/resources/wifi-signal-strength-basics.html
  /* eslint-enable */

  // Handle percentage format (0-100, positive values)
  if (signal >= 0) {
    if (signal >= 75) return 'mdi-wifi-strength-4'
    if (signal >= 50) return 'mdi-wifi-strength-3'
    if (signal >= 25) return 'mdi-wifi-strength-2'
    if (signal >= 10) return 'mdi-wifi-strength-1'
    return 'mdi-wifi-strength-alert-outline'
  }

  // Handle dBm format (negative values)
  if (signal >= -30) return 'mdi-wifi-strength-4'
  if (signal >= -67) return 'mdi-wifi-strength-3'
  if (signal >= -70) return 'mdi-wifi-strength-2'
  if (signal >= -80) return 'mdi-wifi-strength-1'
  return 'mdi-wifi-strength-alert-outline'
}

export function sorted_networks(networks: Network[]): Network[] {
  return networks.sort((a: Network, b: Network) => b.signal - a.signal)
}
