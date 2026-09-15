import { groupBy, partition } from 'lodash'
import { gt as sem_ver_greater, SemVer } from 'semver'

import Notifier from '@/libs/notifier'
import { version_chooser_service } from '@/types/frontend_services'
import {
  DockerLoginInfo,
  LocalVersionsQuery, NestedVersion, Version, VersionsQuery, VersionType,
} from '@/types/version-chooser'
import back_axios from '@/utils/api'

const API_URL = '/version-chooser/v1.0'
const DEFAULT_REMOTE_IMAGE = 'bluerobotics/blueos-core'

const notifier = new Notifier(version_chooser_service)

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

function compareVersions(a: Version, b: Version): number {
  return Date.parse(b.last_modified) - Date.parse(a.last_modified)
}

function sortImages(versions_query: VersionsQuery): VersionsQuery {
  return {
    local: versions_query.local.sort(compareVersions),
    remote: versions_query.remote.sort(compareVersions),
    error: versions_query.error,
  }
}

/** Orders versions so each one is followed by the images committed from it, tagged with their nesting depth */
function nestVersions(versions: Version[]): NestedVersion[] {
  const known_shas = new Set(versions.map(({ sha }) => sha))
  const [children, roots] = partition(
    versions,
    ({ parent_sha, sha }) => parent_sha && parent_sha !== sha && known_shas.has(parent_sha),
  )
  const children_by_parent = groupBy(children, 'parent_sha')

  const nested: NestedVersion[] = []
  // Several tags can point at the same image
  const expanded = new Set<string>()
  const visit = (version: Version, depth: number): void => {
    nested.push({ version, depth })
    if (version.sha === null || expanded.has(version.sha)) {
      return
    }
    expanded.add(version.sha)
    children_by_parent[version.sha]?.forEach((child) => visit(child, depth + 1))
  }
  roots.forEach((root) => visit(root, 0))

  return nested
}

function getLatestBeta(versions_query: VersionsQuery): Version | undefined {
  const ordered_list = sortVersions(
    versions_query.remote
      .filter((image) => isSemVer(image.tag) && image.tag.includes('beta')),
  )
  return ordered_list?.[0]
}

function getLatestStable(versions_query: VersionsQuery): Version | undefined {
  const ordered_list = sortVersions(
    versions_query.remote
      .filter((image) => isSemVer(image.tag) && !image.tag.includes('beta')),
  )
  return ordered_list?.[0]
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

async function loadLocalVersions(): Promise<LocalVersionsQuery> {
  return back_axios({
    method: 'get',
    url: `${API_URL}/version/available/local`,
  }).then((response) => {
    const available_versions = response.data as LocalVersionsQuery
    available_versions.local = available_versions.local.sort(compareVersions)
    return available_versions
  })
}

async function loadAvailableVersions(remote_image_name?: string): Promise<VersionsQuery> {
  remote_image_name = remote_image_name ?? DEFAULT_REMOTE_IMAGE
  return back_axios({
    method: 'get',
    url: `${API_URL}/version/available/${remote_image_name}`,
  }).then((response) => {
    const available_versions = response.data as VersionsQuery
    return sortImages(available_versions)
  })
}

async function loadCurrentVersion(): Promise<Version> {
  return back_axios({
    method: 'get',
    url: `${API_URL}/version/current/`,
  }).then((response) => response.data as Version)
}

async function loadBootstrapCurrentVersion(): Promise<string | undefined> {
  return back_axios({
    method: 'get',
    url: `${API_URL}/bootstrap/current/`,
    // eslint-disable-next-line no-extra-parens
  }).then((response) => (typeof response.data === 'object' ? undefined : response.data))
    // The update process may fail and the user may be in bootstrap-backup
    // This allows us to have the frontend working without crashing
    // But still visible on the back
    .catch((error) => {
      const message = `Failed to fetch bootstrap version: ${error}`
      notifier.pushWarning('VERSION_CHOOSER_FAILED_BOOTSTRAP_VERSION', message)
      return undefined
    })
}

async function commitVersion(repository: string, tag: string): Promise<void> {
  await back_axios({
    method: 'post',
    url: `${API_URL}/version/commit`,
    data: { repository, tag },
    timeout: 2 * 1000,
  })
}

async function dockerLogin(info: DockerLoginInfo): Promise<void> {
  await back_axios({
    method: 'post',
    url: `${API_URL}/docker/login/`,
    data: info,
  })
}

async function dockerLogout(info: DockerLoginInfo): Promise<void> {
  await back_axios({
    method: 'post',
    url: `${API_URL}/docker/logout/`,
    data: info,
  })
}

async function dockerAccounts(): Promise<DockerLoginInfo[]> {
  const data = await back_axios({
    method: 'get',
    url: `${API_URL}/docker/accounts/`,
  })

  return data.data as DockerLoginInfo[]
}

async function getFactoryVersion(): Promise<string> {
  const response = await back_axios({
    method: 'get',
    url: `${API_URL}/version/factory/`,
  })

  return response.data as string
}

export {
  commitVersion,
  DEFAULT_REMOTE_IMAGE,
  dockerAccounts,
  dockerLogin,
  dockerLogout,
  fixVersion,
  getLatestBeta,
  getLatestStable,
  getLatestVersion,
  getVersionType,
  isSemVer,
  loadAvailableVersions,
  loadBootstrapCurrentVersion,
  loadCurrentVersion,
  loadLocalVersions,
  nestVersions,
  sortImages,
  sortVersions,
  getFactoryVersion,
}
