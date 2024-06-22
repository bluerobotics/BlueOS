import semver from 'semver'
import stable from 'semver-stable'

import { Version } from '@/types/kraken'

export function getSortedVersions(versions: Record<string, Version>, reverse = true): Version[] {
  return Object.values(versions).sort((a, b) => semver.compare(a.tag, b.tag))
}

export function getLatestVersion(versions: Record<string, Version>, beta = true): Version | undefined {
  const values = Object.values(versions) ?? []

  if (values.length === 0) {
    return undefined
  }

  if (!beta) {
    return values.find((v) => v.tag === stable.max(values.map((v1) => v1.tag)))
  }

  return values.reduce(
    (a: Version, b: Version) => (semver.compare(a.tag, b.tag) > 0 ? a : b),
  )
}

export function isStable(version: string): boolean {
  return stable.is(version)
}

export function updateAvailableTag(
  versions: Record<string, Version>,
  current: string,
  beta = true,
): undefined | string {
  const latest = getLatestVersion(versions, beta)
  return latest !== undefined && semver.gt(latest.tag, current) ? latest.tag : undefined
}

export default {
  getSortedVersions,
  getLatestVersion,
  isStable,
  updateAvailableTag,
}
