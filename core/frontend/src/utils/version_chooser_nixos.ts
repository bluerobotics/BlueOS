import { gt as sem_ver_greater, parse as parse_sem_ver, SemVer } from 'semver'

import { ReleaseNotes } from '@/types/version-chooser'
import {
  ActivationMode, ActivationResponse, Generation, Release, ReleasesResponse, Status,
} from '@/types/version-chooser-nixos'
import back_axios from '@/utils/api'
import { fetchWithVehicleFallback } from '@/utils/helper_functions'

const API_URL = '/updates/v1.0'
const RELEASES_API_URL = 'https://api.github.com/repos/bluerobotics/BlueOS/releases'
// GitHub's own render keeps the notes identical to the release page, pull request links included
const RELEASE_NOTES_MEDIA_TYPE = 'application/vnd.github.html+json'
const DOCS_URL = 'https://blueos.cloud/docs'

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

function toSemVer(version: string): SemVer | null {
  const fixed_version = fixVersion(version)
  return fixed_version === null ? null : parse_sem_ver(fixed_version)
}

function isSemVer(version: string): boolean {
  // validates a version as SemVer compliant
  return toSemVer(version) !== null
}

function isPreRelease(version: string): boolean {
  const parsed = toSemVer(version)
  return parsed !== null && parsed.prerelease.length > 0
}

/**
 * Newest first. Anything that is not a version (`master`, branch builds) sorts
 * last rather than dropping out: it is still an installable release.
 */
function sortReleases(releases: Release[]): Release[] {
  return [...releases].sort((a, b) => {
    const ver_a = toSemVer(a.version)
    const ver_b = toSemVer(b.version)
    if (ver_a === null || ver_b === null) {
      return ver_a === null ? 1 : -1
    }
    return sem_ver_greater(ver_a, ver_b) ? -1 : 1
  })
}

function latestRelease(releases: Release[], pre_release: boolean): Release | undefined {
  return sortReleases(releases).find((release) => isSemVer(release.version)
    && isPreRelease(release.version) === pre_release)
}

/**
 * The release the vehicle should be offered. A vehicle on a pre-release stays on
 * the pre-release line, which is what someone who opted into beta expects; one on
 * a stable version is only offered stable builds.
 * @param current_version - Version the running generation reports
 */
function getAvailableUpdate(current_version: string, releases: Release[]): Release | undefined {
  const latest_stable = latestRelease(releases, false)
  const latest_beta = latestRelease(releases, true)
  const candidate = isPreRelease(current_version) ? latest_beta : latest_stable

  if (candidate === undefined || candidate.version === current_version) {
    return undefined
  }
  const current = toSemVer(current_version)
  const offered = toSemVer(candidate.version)
  if (current !== null && offered !== null && !sem_ver_greater(offered, current)) {
    return undefined
  }
  return candidate
}

/**
 * The docs site publishes one path per release line (`/docs/1.4/`) up to the current stable one.
 * Pre-releases of a line that is not out yet, and anything that is not a 1.x+ version, are only
 * covered by `/docs/latest/`.
 */
function getDocsUrl(version: string, latest_stable_version?: string): string {
  const parsed = toSemVer(version)
  if (parsed === null || parsed.major < 1) {
    return `${DOCS_URL}/latest/`
  }

  const latest_stable = latest_stable_version ? toSemVer(latest_stable_version) : null
  const release_line = new SemVer(`${parsed.major}.${parsed.minor}.0`)
  const line_is_documented = latest_stable === null
    ? parsed.prerelease.length === 0
    : !sem_ver_greater(release_line, latest_stable)

  return line_is_documented ? `${DOCS_URL}/${parsed.major}.${parsed.minor}/` : `${DOCS_URL}/latest/`
}

/**
 * The daemon answers errors as `{ message }`, which is more useful than axios'
 * generic text, so it is preferred when present.
 */
function describeError(error: unknown): string {
  const candidate = error as { response?: { data?: { message?: string } }, message?: string }
  return candidate?.response?.data?.message ?? candidate?.message ?? `${error}`
}

async function loadStatus(): Promise<Status> {
  return back_axios({
    method: 'get',
    url: `${API_URL}/status`,
  }).then((response) => response.data as Status)
}

async function loadGenerations(): Promise<Generation[]> {
  return back_axios({
    method: 'get',
    url: `${API_URL}/generations`,
  }).then((response) => response.data.generations as Generation[])
}

async function activateGeneration(generation: number, mode: ActivationMode): Promise<ActivationResponse> {
  return back_axios({
    method: 'post',
    url: `${API_URL}/generations/${generation}/activate`,
    params: { mode },
  }).then((response) => response.data as ActivationResponse)
}

async function deleteGeneration(generation: number): Promise<void> {
  await back_axios({
    method: 'delete',
    url: `${API_URL}/generations/${generation}`,
  })
}

async function restartCore(): Promise<void> {
  await back_axios({
    method: 'post',
    url: `${API_URL}/restart`,
  })
}

/**
 * The manifest is remote, so an unreachable publisher is reported alongside the
 * list instead of being thrown: the generations on the card are still usable.
 */
async function loadReleases(): Promise<ReleasesResponse> {
  return back_axios({
    method: 'get',
    url: `${API_URL}/releases`,
  }).then((response) => response.data as ReleasesResponse)
}

async function activateRelease(version: string, mode: ActivationMode): Promise<ActivationResponse> {
  return back_axios({
    method: 'post',
    url: `${API_URL}/releases/${version}/activate`,
    params: { mode },
    timeout: 30 * 60 * 1000, // the closure comes from a binary cache, which can be slow
  }).then((response) => response.data as ActivationResponse)
}

async function downloadRelease(version: string): Promise<void> {
  await back_axios({
    method: 'post',
    url: `${API_URL}/releases/${version}/download`,
    timeout: 30 * 60 * 1000,
  })
}

interface GitHubRelease {
  body_html: string | null,
  html_url: string,
}

const release_notes_requests = new Map<string, Promise<ReleaseNotes | undefined>>()

async function requestReleaseNotes(version: string): Promise<ReleaseNotes | undefined> {
  try {
    const response = await fetchWithVehicleFallback(
      `${RELEASES_API_URL}/tags/${version}`,
      { Accept: RELEASE_NOTES_MEDIA_TYPE },
    )
    if (!response.ok) {
      return undefined
    }
    const release = await response.json() as GitHubRelease
    if (!release.body_html) {
      return undefined
    }
    // GitHub renders anchors without a target, and following one would navigate BlueOS away
    return {
      html: release.body_html.replaceAll('<a ', '<a target="_blank" rel="noopener noreferrer" '),
      url: release.html_url,
    }
  } catch {
    return undefined
  }
}

/**
 * Only versions with a GitHub release are covered: `master`, branch builds and
 * custom tags answer with a 404. Notes are cosmetic, so an unreachable GitHub
 * reads as "no notes". Answers are shared between every card asking for the same
 * version, and misses are forgotten so a vehicle that comes online later can
 * still get the notes.
 * @param version - Version string, e.g. `1.4.5` or `1.5.0-beta.42`
 */
async function getReleaseNotes(version: string): Promise<ReleaseNotes | undefined> {
  const fixed_version = fixVersion(version)
  if (fixed_version === null) {
    return undefined
  }

  let request = release_notes_requests.get(fixed_version)
  if (request === undefined) {
    request = requestReleaseNotes(fixed_version)
    release_notes_requests.set(fixed_version, request)
    request.then((notes) => {
      if (notes === undefined) {
        release_notes_requests.delete(fixed_version)
      }
    })
  }
  return request
}

export {
  activateGeneration,
  activateRelease,
  deleteGeneration,
  describeError,
  downloadRelease,
  getAvailableUpdate,
  getDocsUrl,
  getReleaseNotes,
  isPreRelease,
  isSemVer,
  latestRelease,
  loadGenerations,
  loadReleases,
  loadStatus,
  restartCore,
  sortReleases,
}
