import axios from 'axios'

import { fetchInstalledExtensions } from '@/components/kraken/KrakenManager'
import { InstalledExtensionData } from '@/types/kraken'
import back_axios from '@/utils/api'

export const MAJOR_TOM_IDENTIFIER = 'blueos.major_tom'
export const MAJOR_TOM_INSTALL_URL = 'https://blueos.cloud/major_tom/install/'

const KRAKEN_API_V2_URL = '/kraken/v2.0'

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
  progressHandler: (event: { event: { currentTarget: { response: string } } }) => void,
): Promise<void> {
  const majorTomData = await fetchMajorTomInstallData()

  await back_axios({
    method: 'POST',
    url: `${KRAKEN_API_V2_URL}/extension/`,
    data: {
      identifier: majorTomData.identifier,
      name: majorTomData.name,
      docker: majorTomData.docker,
      tag: majorTomData.tag,
      enabled: true,
      permissions: majorTomData?.permissions ?? '',
      user_permissions: majorTomData?.user_permissions ?? '',
    },
    timeout: 600000,
    onDownloadProgress: progressHandler,
  })
}
