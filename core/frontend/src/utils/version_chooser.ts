import { gt as sem_ver_greater, SemVer } from 'semver'
import {
  Action,
  getModule,
  Module,
  Mutation,
  VuexModule,
} from 'vuex-module-decorators'

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

function sortVersions(versions: string[]): string[] {
  return versions.sort(
    (a: string, b: string) => {
      const ver_a = fixVersion(a)
      const ver_b = fixVersion(b)
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

function getLatestBeta(versions_query: VersionsQuery): string | undefined {
  const ordered_list = sortVersions(
    versions_query.remote.map((image) => image.tag)
      .filter((tag) => isSemVer(tag) && tag.includes('beta')),
  )
  return ordered_list ? ordered_list[0] : undefined
}

function getLatestStable(versions_query: VersionsQuery): string | undefined {
  const ordered_list = sortVersions(
    versions_query.remote.map((image) => image.tag)
      .filter((tag) => isSemVer(tag) && !tag.includes('beta')),
  )
  return ordered_list ? ordered_list[0] : undefined
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
  getVersionType,
  isSemVer,
  loadAvailableVersions,
  loadCurrentVersion,
  sortImages,
  sortVersions,
}
