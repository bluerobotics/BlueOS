import { gt as sem_ver_greater, SemVer } from 'semver'

import { Version, VersionsQuery, VersionType } from '@/types/version-chooser'
import back_axios from '@/utils/api'

const API_URL = '/version-chooser/v1.0/version'
const DEFAULT_REMOTE_IMAGE = 'bluerobotics/blueos-core'

function fixVersion(version: string): string | null {
  /** It turned out that our semvers are wrong... oopss
  This turns 1.0.0.beta12 into 1.0.0-beta.12
  Additionally filters out tags with no '.' in it, which
  can be improved
  */
  if (version.includes('.beta')) {
    return version.replace('.beta', '-beta.')
  }
  if (!version.includes('.')) {
    return null
  }
  return version
}

function isSemVer(version: string): boolean {
  // validates a version as SemVer compliant
  const fixed_version = fixVersion(version)
  if (fixed_version == null) {
    return false
  }

  try {
    const semver = new SemVer(fixed_version)
    return semver !== null
  } catch (error) {
    return false
  }
}

function getVersionType(version: Version | null) : VersionType | undefined {
  const tag = version?.tag
  if (tag === undefined) {
    return undefined
  }

  if (tag === 'master') { return VersionType.Master }
  if (isSemVer(tag) && tag.includes('beta')) { return VersionType.Beta }
  if (isSemVer(tag) && !tag.includes('beta')) { return VersionType.Stable }
  return VersionType.Custom
}

function sortVersions(versions: Version[]): Version[] {
  return versions.sort(
    (a: Version, b: Version) => {
      const ver_a = fixVersion(a.tag)
      const ver_b = fixVersion(b.tag)
      if (ver_a === null) {
        return 1
      }
      if (ver_b === null) {
        return -1
      }
      return sem_ver_greater(new SemVer(ver_a), new SemVer(ver_b)) === true ? -1 : 1
    },
  )
}

function sortImages(versions_query: VersionsQuery): VersionsQuery {
  return {
    local: versions_query.local.sort(
      (a: Version, b: Version) => Date.parse(b.last_modified) - Date.parse(a.last_modified),
    ),
    remote: versions_query.remote.sort(
      (a: Version, b: Version) => Date.parse(b.last_modified) - Date.parse(a.last_modified),
    ),
    error: versions_query.error,
  }
}

function getLatestBeta(versions_query: VersionsQuery): Version | undefined {
  const ordered_list = sortVersions(
    versions_query.remote
      .filter((image) => isSemVer(image.tag) && image.tag.includes('beta')),
  )
  return ordered_list ? ordered_list[0] : undefined
}

function getLatestStable(versions_query: VersionsQuery): Version | undefined {
  const ordered_list = sortVersions(
    versions_query.remote
      .filter((image) => isSemVer(image.tag) && !image.tag.includes('beta')),
  )
  return ordered_list ? ordered_list[0] : undefined
}

function getMaster(versions_query: VersionsQuery): Version | undefined {
  return versions_query.remote.find((version: Version) => version.tag === 'master')
}

function getLatestVersion(versions_query: VersionsQuery, current_version: Version): Version | undefined {
  const beta_version = getLatestBeta(versions_query)
  const stable_version = getLatestStable(versions_query)

  switch (getVersionType(current_version)) {
    case VersionType.Master:
      return getMaster(versions_query)

    case VersionType.Beta: {
      let last_version = beta_version
      if (stable_version !== undefined && beta_version !== undefined) {
        [last_version] = sortVersions([stable_version, beta_version])
      }
      return versions_query.remote.find((version) => version.tag === last_version?.tag)
    }

    case VersionType.Stable: {
      return versions_query.remote.find((version) => version.tag === stable_version?.tag)
    }

    case VersionType.Custom:
    default:
      return undefined
  }
}

async function loadAvailableVersions(remote_image_name?: string): Promise<VersionsQuery> {
  remote_image_name = remote_image_name ?? DEFAULT_REMOTE_IMAGE
  return back_axios({
    method: 'get',
    url: `${API_URL}/available/${remote_image_name}`,
  }).then((response) => {
    const available_versions = response.data as VersionsQuery
    const { error } = response.data
    if (error && error !== '') {
      throw new Error(`Error: ${error}`)
    }
    return sortImages(available_versions)
  })
}

async function loadCurrentVersion(): Promise<Version> {
  return back_axios({
    method: 'get',
    url: `${API_URL}/current/`,
  }).then((response) => response.data as Version)
}

export {
  fixVersion,
  getLatestBeta,
  getLatestStable,
  getLatestVersion,
  getVersionType,
  isSemVer,
  loadAvailableVersions,
  loadCurrentVersion,
  sortImages,
  sortVersions,
}
