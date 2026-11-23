import axios from 'axios'

import { fetchInstalledExtensions, installExtension } from '@/components/kraken/KrakenManager'
import { InstalledExtensionData, ProgressEvent } from '@/types/kraken'

export const MAJOR_TOM_IDENTIFIER = 'blueos.major_tom'
export const MAJOR_TOM_INSTALL_URL = 'https://blueos.cloud/major_tom/install/'

export type MajorTomAction = 'skip' | 'install' | 'update'

export async function fetchMajorTomInstallData(): Promise<InstalledExtensionData> {
  const response = await axios.get(MAJOR_TOM_INSTALL_URL)
  return response.data as InstalledExtensionData
}

export async function getInstalledMajorTom(): Promise<InstalledExtensionData | undefined> {
  const extensions = await fetchInstalledExtensions()
  return extensions.find((extension) => extension.identifier === MAJOR_TOM_IDENTIFIER)
}

export async function resolveMajorTomAction(hasInternet: boolean): Promise<MajorTomAction> {
  if (!hasInternet) {
    return 'skip'
  }

  const [installed, latest] = await Promise.all([
    getInstalledMajorTom(),
    fetchMajorTomInstallData(),
  ])

  if (!installed) {
    return 'install'
  }

  if (installed.tag !== latest.tag) {
    return 'update'
  }

  return 'skip'
}

export async function installOrUpdateMajorTom(
  progressHandler: (event: { event: ProgressEvent }) => void,
): Promise<void> {
  const majorTomData = await fetchMajorTomInstallData()

  // axios' fetch adapter leaves `.event` undefined, the callers need the native ProgressEvent in any case
  await installExtension(majorTomData, (progressEvent) => progressHandler({
    event: progressEvent.event ?? (progressEvent as unknown as ProgressEvent),
  }))
}
