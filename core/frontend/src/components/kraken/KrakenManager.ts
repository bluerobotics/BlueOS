import { QueryTarget, Sample, Subscriber } from '@eclipse-zenoh/zenoh-ts'

import zenoh from '@/libs/zenoh'
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
import { createDeferred } from '@/utils/deferred'

const KRAKEN_BASE_URL = '/kraken'
const KRAKEN_API_V2_URL = `${KRAKEN_BASE_URL}/v2.0`
const KRAKEN_BASE_ZENOH = 'kraken'
const INSTALL_PROGRESS_TOPIC = `${KRAKEN_BASE_ZENOH}/extension/install/progress`
const ZENOH_QUERY_STANDARD_TIMEOUT = 10000


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

function buildInstallQueryKey(identifier: string, tag: string | undefined, stable: boolean): string {
  let key = `${KRAKEN_BASE_ZENOH}/extension/install?identifier=${encodeURIComponent(identifier)}`
  if (tag) key += `;tag=${encodeURIComponent(tag)}`
  if (!stable) key += ';stable=false'
  return key
}

type InstallSample =
  | { kind: 'error'; message: string }
  | { kind: 'complete' }
  | { kind: 'progress'; raw: string }
  | null

function parseInstallSample(raw: string, identifier: string): InstallSample {
  let data: { identifier?: string; status?: string; error?: string }
  try {
    data = JSON.parse(raw)
  } catch {
    return null
  }
  if (data.identifier !== identifier) return null
  if (data.error) return { kind: 'error', message: data.error }
  if (data.status === 'complete') return { kind: 'complete' }
  return { kind: 'progress', raw }
}

/**
 * Install an extension to the latest version available. 
 * The backend publishes the pull progress on `INSTALL_PROGRESS_TOPIC`.
 *
 * @param {string} identifier The identifier of the extension
 * @param {function} progressHandler The progress handler for the download
 * @param {string} tag The tag of the extension
 * @param {boolean} stable If true, will install the latest stable version, default is true
 * @param {number} timeout The timeout for the install
 */
export async function installExtension(
  identifier: string,
  progressHandler?: (fragment: string) => void,
  tag?: string,
  stable = true,
  timeout = 600000,
): Promise<void> {
  const deferred = createDeferred<void>()
  let subscriber: Subscriber | null = null
  let timer: ReturnType<typeof setTimeout> | null = null

  async function cleanup(): Promise<void> {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    try {
      await subscriber?.undeclare()
    } catch {
      // The subscriber may already be gone. Ignore cleanup errors.
    }
    subscriber = null
  }

  async function handleSample(sample: Sample): Promise<void> {
    const result = parseInstallSample(sample.payload().to_string(), identifier)
    if (result === null) return
    switch (result.kind) {
      case 'error':
        cleanup().finally(() => deferred.reject(new Error(result.message)))
        break
      case 'complete':
        cleanup().finally(() => deferred.resolve())
        break
      case 'progress':
        progressHandler?.(result.raw)
        break
      default:
        break
    }
  }

  // Subscribe before triggering the install.
  subscriber = await zenoh.subscriber(INSTALL_PROGRESS_TOPIC, handleSample)
  if (!subscriber) {
    throw new Error('Failed to subscribe to install progress topic')
  }
  timer = setTimeout(
    () => cleanup().finally(() => deferred.reject(new Error(`Install timed out after ${timeout}ms`))),
    timeout,
  )

  try {
    const reply = await zenoh.query(
      buildInstallQueryKey(identifier, tag, stable),
      QueryTarget.BestMatching,
      timeout,
    )
    if (!reply || reply.error) {
      throw new Error(reply?.error ?? 'Install query failed')
    }
  } catch (error) {
    await cleanup()
    throw error
  }

  return deferred.promise
}

/**
 * Enable an extension by its identifier and tag, uses zenoh
 * @param {string} identifier The identifier of the extension
 * @param {string} tag The tag of the extension
 */
export async function enableExtension(identifier: string, tag: string): Promise<void> {
  await zenoh.query(
    `${KRAKEN_BASE_ZENOH}/extension/enable?identifier=${encodeURIComponent(identifier)};tag=${encodeURIComponent(tag)}`,
    QueryTarget.BestMatching,
    ZENOH_QUERY_STANDARD_TIMEOUT,
  )
}

/**
 * Disable an extension by its identifier, uses zenoh
 * @param {string} identifier The identifier of the extension
 */
export async function disableExtension(identifier: string): Promise<void> {
  await zenoh.query(
    `${KRAKEN_BASE_ZENOH}/extension/disable?identifier=${encodeURIComponent(identifier)}`,
    QueryTarget.BestMatching,
    ZENOH_QUERY_STANDARD_TIMEOUT,
  )
}

/**
 * Uninstall an extension by its identifier, uses zenoh
 * @param {string} identifier The identifier of the extension
 */
export async function uninstallExtension(identifier: string, tag?: string): Promise<void> {
  let queryKey = `${KRAKEN_BASE_ZENOH}/extension/uninstall?identifier=${encodeURIComponent(identifier)}`
  if (tag) queryKey += `;tag=${encodeURIComponent(tag)}`

  await zenoh.query(
    queryKey,
    QueryTarget.BestMatching,
    ZENOH_QUERY_STANDARD_TIMEOUT,
  )
}

/**
 * Restart an extension by its identifier, uses zenoh
 * @param {string} identifier The identifier of the extension
 */
export async function restartExtension(identifier: string): Promise<void> {
  await zenoh.query(
    `${KRAKEN_BASE_ZENOH}/extension/restart?identifier=${encodeURIComponent(identifier)}`,
    QueryTarget.BestMatching,
    ZENOH_QUERY_STANDARD_TIMEOUT,
  )
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
 * List details of all installed extensions.
 * @returns {Promise<InstalledExtensionData[]> | null}
 */
export async function fetchInstalledExtensions(): Promise<InstalledExtensionData[] | null> {
  return zenoh.query(
    `${KRAKEN_BASE_ZENOH}/extension/fetch`, 
    QueryTarget.BestMatching,
    30000,
  )
}

/**
 * List all running containers from kraken, uses zenoh.
 */
export async function listContainers(): Promise<RunningContainer[] | null> {
  return zenoh.query(
    `${KRAKEN_BASE_ZENOH}/container/fetch`,
    QueryTarget.BestMatching,
    ZENOH_QUERY_STANDARD_TIMEOUT,
  )
}

/**
 * List all stats of all running containers from kraken, uses zenoh.
 */
export async function getContainersStats(): Promise<any | null> {
  return zenoh.query(
    `${KRAKEN_BASE_ZENOH}/container/stats`,
    QueryTarget.BestMatching,
    ZENOH_QUERY_STANDARD_TIMEOUT,
  )
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
  await zenoh.query(
    `${KRAKEN_BASE_ZENOH}/extension/upload/keep-alive?temp_tag=${encodeURIComponent(tempTag)}`,
    QueryTarget.BestMatching,
    ZENOH_QUERY_STANDARD_TIMEOUT,
  )
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

/**
 * Request historical logs for an extension
 * @param {string} identifier The identifier of the extension
 * @param {number} timeout The timeout for the query
 * @returns {Promise<any | null>}
 */
export async function getHistoricalLogsForExtension(identifier: string, timeout: number): Promise<any | null> {
  const queryKey = `${KRAKEN_BASE_ZENOH}/container/logs/request?extension_name=${identifier}`
  return await zenoh.query(queryKey, QueryTarget.BestMatching, timeout)
}

/**
 * Create a new subscriber for a given topic
 * @param {string} topic The topic to subscribe to
 * @param {function} subscriberHandler The handler for the topic
 * @returns {Promise<Subscriber | null>}
 */
export async function createExtensionLogsSubscriber(
  topic: string,
  subscriberHandler: (sample: Sample) => Promise<void>,
) : Promise<Subscriber | null> {
  return await zenoh.subscriber(topic, subscriberHandler)
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
  installExtension,
  enableExtension,
  disableExtension,
  uninstallExtension,
  restartExtension,
  listContainers,
  getContainersStats,
  uploadExtensionTarFile,
  keepTemporaryExtensionAlive,
  finalizeExtension,
  getHistoricalLogsForExtension,
  createExtensionLogsSubscriber,
}
