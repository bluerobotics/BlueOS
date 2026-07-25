// Must match linux2rest Sampler interval (src/main.rs: Duration::from_secs(5)).
// TODO: prefer a probed interval if/when linux2rest exposes it (Mbps silently drift if Sampler cadence changes).
export const LINUX2REST_SYSTEM_SAMPLE_INTERVAL_S = 5

/** Convert a linux2rest per-sample byte delta into a bytes-per-second rate. Negative deltas are clamped to zero. */
export function networkProbeRateBps(bytesSinceLastProbe: number): number {
  return Math.max(0, bytesSinceLastProbe) / LINUX2REST_SYSTEM_SAMPLE_INTERVAL_S
}

export function formatBandwidth(bytesPerSecond: number): string {
  const mbps = (8 * bytesPerSecond / 1024 / 1024)
  const decimal_places = mbps < 10 ? 2 : mbps < 100 ? 1 : 0
  return `${mbps.toFixed(decimal_places)}Mbps`
}
