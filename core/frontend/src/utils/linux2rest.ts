// Must match linux2rest Sampler interval (src/main.rs: Duration::from_secs(5)).
// TODO: prefer a probed interval if/when linux2rest exposes it (rates silently drift if Sampler cadence changes).
export const LINUX2REST_SYSTEM_SAMPLE_INTERVAL_S = 5

/** Convert a linux2rest per-sample byte delta into a bytes-per-second rate. Negative deltas are clamped to zero. */
export function linux2restProbeRateBps(bytesSinceLastProbe: number): number {
  return Math.max(0, bytesSinceLastProbe) / LINUX2REST_SYSTEM_SAMPLE_INTERVAL_S
}
