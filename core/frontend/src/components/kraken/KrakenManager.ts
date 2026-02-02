import {
  ExtensionData,
  ExtensionUploadResponse,
  InstalledExtensionData,
  Manifest,
  ManifestSource,
  RunningContainer,
  UploadProgressEvent,
} from '@/types/kraken'
import back_axios from '@/utils/api'

const KRAKEN_BASE_URL = '/kraken'
const KRAKEN_API_V2_URL = `${KRAKEN_BASE_URL}/v2.0`

/**
 * List details of all installed extensions.
 * @returns {Promise<InstalledExtensionData[]>}
 */
export async function fetchInstalledExtensions(): Promise<InstalledExtensionData[]> {
  const response = await back_axios({
    method: 'get',
    url: `${KRAKEN_API_V2_URL}/extension/`,
    timeout: 10000,
  })

  return response.data as InstalledExtensionData[]
}

/**
 * List all manifest sources from kraken, uses API v2
 * @param {boolean} data If true, will also include manifest data in the response, default is true
 * @param {boolean} enabled If true, will only return enabled manifest sources, default is false
 * @returns {Promise<Manifest[]>}
 */
export async function fetchManifestSources(data = true, enabled = false): Promise<Manifest[]> {
  const timeout = data ? 25000 : 10000

  const response = await back_axios({
    method: 'get',
    url: `${KRAKEN_API_V2_URL}/manifest/?data=${data}&enabled=${enabled}`,
    timeout,
  })

  return response.data as Manifest[]
}

/**
 * Fetch a specific manifest source from kraken, uses API v2
 * @param {string} identifier The identifier of the manifest source
 * @param {boolean} data If true, will also include manifest data in the response, default is true
 * @returns {Promise<Manifest>}
 */
export async function fetchManifestSource(identifier: string, data = true): Promise<Manifest> {
  const response = await back_axios({
    method: 'get',
    url: `${KRAKEN_API_V2_URL}/manifest/${identifier}/details?data=${data}`,
    timeout: 15000,
  })

  return response.data as Manifest
}

/**
 * Fetch all manifests from kraken in a single merged representation, repeated entries will be excluded, only the one
 * present in the manifest wth higher priority will be kept, uses API v2
 * @returns {Promise<ExtensionData[]>}
 */
export async function fetchConsolidatedManifests(): Promise<ExtensionData[]> {
  const response = await back_axios({
    method: 'get',
    url: `${KRAKEN_API_V2_URL}/manifest/consolidated`,
    timeout: 25000,
  })

  return (response.data as ExtensionData[]).map((extension: ExtensionData) => ({
    ...extension,
    is_compatible: Object.values(extension.versions).some(
      (version) => version.images.some((image) => image.compatible),
    ),
  }))
}

/**
 * Creates a new manifest source in kraken, uses API v2
 * @param {boolean} validateUrl If true, will throw in case an invalid manifest source is provided in given URL
 * @returns {Promise<Manifest>} The created manifest source with data already fetched in case validate is true,
 * default is true
 */
export async function addManifestSource(source: ManifestSource, validateUrl = true): Promise<Manifest> {
  const response = await back_axios({
    method: 'post',
    url: `${KRAKEN_API_V2_URL}/manifest/?validate_url=${validateUrl}`,
    data: source,
    timeout: 15000,
  })

  return response.data as Manifest
}

/**
 * Updates a manifest source in kraken, uses API v2
 * @param {string} identifier The identifier of the manifest source
 * @param {ManifestSource} source The updated manifest source data
 * @param {boolean} validateUrl If true, will throw in case an invalid manifest source is provided in given URL,
 * default is true
 * @returns {Promise<void>}
 */
export async function updateManifestSource(
  identifier: string,
  source: ManifestSource,
  validateUrl = true,
): Promise<void> {
  await back_axios({
    method: 'put',
    url: `${KRAKEN_API_V2_URL}/manifest/${identifier}/details?validate_url=${validateUrl}`,
    data: source,
    timeout: 10000,
  })
}

/**
 * Deletes a manifest source in kraken, uses API v2
 * @param {string} identifier The identifier of the manifest source
 * @returns {Promise<void>}
 */
export async function deleteManifestSource(identifier: string): Promise<void> {
  await back_axios({
    method: 'delete',
    url: `${KRAKEN_API_V2_URL}/manifest/${identifier}`,
    timeout: 10000,
  })
}

/**
 * Enables a manifest source in kraken, uses API v2
 * @param {string} identifier The identifier of the manifest source
 * @returns {Promise<void>}
 */
export async function enabledManifestSource(identifier: string): Promise<void> {
  await back_axios({
    method: 'post',
    url: `${KRAKEN_API_V2_URL}/manifest/${identifier}/enable`,
    timeout: 10000,
  })
}

/**
 * Disables a manifest source in kraken, uses API v2
 * @param {string} identifier The identifier of the manifest source
 * @returns {Promise<void>}
 */
export async function disabledManifestSource(identifier: string): Promise<void> {
  await back_axios({
    method: 'post',
    url: `${KRAKEN_API_V2_URL}/manifest/${identifier}/disable`,
    timeout: 10000,
  })
}

/**
 * Reorders manifest sources in kraken based on a list of identifiers, if some identifier is present in the backend
 * it will be append at the end of the new order list on the backend, uses API v2
 * @param {string[]} order The list of manifest sources identifiers in the new order
 * @returns {Promise<void>}
 */
export async function setManifestSourcesOrders(order: string[]): Promise<void> {
  await back_axios({
    method: 'put',
    url: `${KRAKEN_API_V2_URL}/manifest/orders`,
    data: order,
    timeout: 10000,
  })
}

/**
 * Reorder a specific manifest source in kraken, if some source is already using this order, will be pushed to
 * the next number, the same apply for others following, uses API v2
 * @param {string} identifier The identifier of the manifest source to be reordered
 * @param {number} order The new order for the manifest source
 */
export async function setManifestSourceOrder(identifier: string, order: number): Promise<void> {
  await back_axios({
    method: 'put',
    url: `${KRAKEN_API_V2_URL}/manifest/${identifier}/order/${order}'`,
    timeout: 10000,
  })
}

/**
 * Install an extension to the latest version available
 * @param {InstalledExtensionData} extension The extension to be installed
 * @param {function} progressHandler The progress handler for the download
 */
export async function installExtension(
  extension: InstalledExtensionData,
  progressHandler: (event: any) => void,
): Promise<void> {
  await back_axios({
    url: `${KRAKEN_API_V2_URL}/extension/install`,
    method: 'POST',
    data: {
      identifier: extension.identifier,
      name: extension.name,
      docker: extension.docker,
      tag: extension.tag,
      enabled: true,
      permissions: extension?.permissions ?? '',
      user_permissions: extension?.user_permissions ?? '',
    },
    timeout: 600000,
    onDownloadProgress: progressHandler,
  })
}

/**
 * Enable an extension by its identifier and tag, uses API v2
 * @param {string} identifier The identifier of the extension
 * @param {string} tag The tag of the extension
 */
export async function enableExtension(identifier: string, tag: string): Promise<void> {
  await back_axios({
    method: 'POST',
    url: `${KRAKEN_API_V2_URL}/extension/${identifier}/${tag}/enable`,
    timeout: 10000,
  })
}

/**
 * Disable an extension by its identifier, uses API v2
 * @param {string} identifier The identifier of the extension
 */
export async function disableExtension(identifier: string): Promise<void> {
  await back_axios({
    method: 'POST',
    url: `${KRAKEN_API_V2_URL}/extension/${identifier}/disable`,
    timeout: 10000,
  })
}

/**
 * Uninstall an extension by its identifier, uses API v2
 * @param {string} identifier The identifier of the extension
 */
export async function uninstallExtension(identifier: string): Promise<void> {
  await back_axios({
    method: 'DELETE',
    url: `${KRAKEN_API_V2_URL}/extension/${identifier}`,
  })
}

/**
 * Restart an extension by its identifier, uses API v2
 * @param {string} identifier The identifier of the extension
 */
export async function restartExtension(identifier: string): Promise<void> {
  await back_axios({
    method: 'POST',
    url: `${KRAKEN_API_V2_URL}/extension/${identifier}/restart`,
    timeout: 10000,
  })
}

/**
 * Update an extension to a specific version, uses API v2
 * @param {string} identifier The identifier of the extension
 * @param {string} version The version of the extension
 * @param {function} progressHandler The progress handler for the download
 */
export async function updateExtensionToVersion(
  identifier: string,
  version: string,
  progressHandler: (event: any) => void,
): Promise<void> {
  await back_axios({
    url: `${KRAKEN_API_V2_URL}/extension/${identifier}/${version}`,
    method: 'PUT',
    timeout: 120000,
    onDownloadProgress: progressHandler,
  })
}

/**
 * List all installed extensions from kraken, uses API v2
 */
export async function getInstalledExtensions(): Promise<InstalledExtensionData[]> {
  const response = await back_axios({
    method: 'GET',
    url: `${KRAKEN_API_V2_URL}/extension/`,
    timeout: 30000,
  })

  return response.data as InstalledExtensionData[]
}

/**
 * List all running containers from kraken, uses API v2
 */
export async function listContainers(): Promise<RunningContainer[]> {
  const response = await back_axios({
    method: 'GET',
    url: `${KRAKEN_API_V2_URL}/container/`,
    timeout: 30000,
  })

  return response.data as RunningContainer[]
}

/**
 * List all stats of all running containers from kraken, uses API v2
 */
export async function getContainersStats(): Promise<any> {
  const response = await back_axios({
    method: 'GET',
    url: `${KRAKEN_API_V2_URL}/container/stats`,
    timeout: 20000,
  })

  return response.data
}

/**
 * Fetch logs of a given container.
 * @param {string} containerName The name of the container
 * @param {function} progressHandler The progress handler for the download
 * @param {AbortSignal} cancelToken The cancel token for the request
 */
export async function getContainerLogs(
  containerName: string,
  progressHandler: (event: any) => void,
  cancelToken: AbortSignal | undefined,
): Promise<any> {
  await back_axios({
    method: 'GET',
    url: `${KRAKEN_API_V2_URL}/container/${containerName}/log`,
    onDownloadProgress: progressHandler,
    signal: cancelToken,
  })
}

/**
 * Upload a tar file containing a Docker image and extract metadata
 * @param {File} file The tar file to upload
 * @returns {Promise<{temp_tag: string, metadata: any, image_name: string}>}
 */
export async function uploadExtensionTarFile(
  file: File,
  progressHandler?: (event: UploadProgressEvent) => void,
): Promise<ExtensionUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await back_axios({
    method: 'POST',
    url: `${KRAKEN_API_V2_URL}/extension/upload`,
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 120000,
    onUploadProgress: progressHandler,
  })

  return response.data
}

/**
 * Keep a temporary uploaded extension alive while the user configures metadata.
 * @param {string} tempTag The temporary tag returned by the upload endpoint
 * @returns {Promise<void>}
 */
export async function keepTemporaryExtensionAlive(tempTag: string): Promise<void> {
  await back_axios({
    method: 'POST',
    url: `${KRAKEN_API_V2_URL}/extension/upload/keep-alive?temp_tag=${tempTag}`,
    timeout: 10000,
  })
}

/**
 * Finalize a temporary extension by assigning a valid identifier and installing it
 * @param {InstalledExtensionData} extension The extension data to finalize
 * @param {string} tempTag The temporary tag from upload response
 * @param {function} progressHandler The progress handler for the download
 * @returns {Promise<void>}
 */
export async function finalizeExtension(
  extension: InstalledExtensionData,
  tempTag: string,
  progressHandler: (event: any) => void,
): Promise<void> {
  await back_axios({
    method: 'POST',
    url: `${KRAKEN_API_V2_URL}/extension/upload/finalize?temp_tag=${tempTag}`,
    data: {
      identifier: extension.identifier,
      name: extension.name,
      docker: extension.docker,
      tag: extension.tag,
      enabled: true,
      permissions: extension?.permissions ?? '',
      user_permissions: extension?.user_permissions ?? '',
    },
    timeout: 120000,
    onDownloadProgress: progressHandler,
  })
}

export default {
  fetchManifestSources,
  fetchManifestSource,
  fetchConsolidatedManifests,
  fetchInstalledExtensions,
  addManifestSource,
  updateManifestSource,
  deleteManifestSource,
  enabledManifestSource,
  disabledManifestSource,
  setManifestSourcesOrders,
  setManifestSourceOrder,
  updateExtensionToVersion,
  installExtension,
  getInstalledExtensions,
  enableExtension,
  disableExtension,
  uninstallExtension,
  restartExtension,
  listContainers,
  getContainersStats,
  getContainerLogs,
  uploadExtensionTarFile,
  keepTemporaryExtensionAlive,
  finalizeExtension,
}
