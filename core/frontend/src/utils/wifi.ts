import { Network } from '@/types/wifi'

export function wifi_strenght_icon(signal_db: number): string {
  /*eslint-disable */
  // | Signal Strength | TL;DR     |  Description                                                                                                                               |
  // |-----------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------|
  // | -30 dBm         | Amazing   | Max achievable signal strength. The client can only be a few feet from the AP to achieve this. Not typical or desirable in the real world. |
  // | -67 dBm         | Very Good | Minimum signal strength for applications that require very reliable, timely delivery of data packets.                                      |
  // | -70 dBm         | Okay      | Minimum signal strength for reliable packet delivery.                                                                                      |
  // | -80 dBm         | Not Good  | Minimum signal strength for basic connectivity. Packet delivery may be unreliable.                                                         |
  // | -90 dBm         | Unusable  | Approaching or drowning in the noise floor. Any functionality is highly unlikely.                                                           |
  // Reference: metageek.com/training/resources/wifi-signal-strength-basics.html
  /* eslint-enable */

  if (signal_db >= -30) return 'mdi-wifi-strength-4'
  if (signal_db >= -67) return 'mdi-wifi-strength-3'
  if (signal_db >= -70) return 'mdi-wifi-strength-2'
  if (signal_db >= -80) return 'mdi-wifi-strength-1'
  return 'mdi-wifi-strength-alert-outline'
}

export function sorted_networks(networks: Network[]): Network[] {
  return networks.sort((a: Network, b: Network) => b.signal - a.signal)
}
