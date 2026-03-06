export function formatBandwidth(bytesPerSecond: number): string {
  const mbps = (8 * Math.max(0, bytesPerSecond) / 1024 / 1024)
  const decimal_places = mbps < 10 ? 2 : mbps < 100 ? 1 : 0
  return `${mbps.toFixed(decimal_places)}Mbps`
}
