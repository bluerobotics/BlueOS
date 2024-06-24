import {
  ExtensionData,
  InstalledExtensionData,
  Manifest,
  ManifestSource,
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
}
