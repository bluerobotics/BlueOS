import axios, { AxiosInstance } from 'axios'

import frontend from '@/store/frontend'

const backend_offline_error = new Error('Backend is offline')
backend_offline_error.name = 'BackendOffline'
export { backend_offline_error }

export const isBackendOffline = (error: any): boolean => {
  if (error === backend_offline_error) { return true }
  if (error.message === 'Network Error') { return true }
  return false;
}

// Every back_axios call used to hit /status first, which piled up under normal polling.
// Cache a recent "online" result for 3s (same cadence as BackendStatusChecker.vue's UI poll;
// that component only reads frontend.backend_offline -- it does not hit /status itself).
// Offline is never cached.
const STATUS_TTL_MS = 3000

let last_online_at = 0

function applyStatusResult(backend_offline: boolean): void {
  frontend.setBackendOffline(backend_offline)
  if (!backend_offline) {
    last_online_at = Date.now()
  }
}

const axios_backend_instance: AxiosInstance = axios.create()
axios_backend_instance.interceptors.request.use(async (config) => {
  const is_recently_online = last_online_at > 0 && !frontend.backend_offline
  if (is_recently_online && (Date.now() - last_online_at) < STATUS_TTL_MS) {
    return config
  }

  // Still recently online: refresh /status in the background, but do not block this request.
  if (is_recently_online) {
    if (frontend.backend_status_request === null) {
      const request = axios.get(frontend.backend_status_url, { timeout: 5000 })
      frontend.setBackendStatusRequest(request)
      request
        .then((response) => {
          applyStatusResult(response.status !== 204)
        })
        .catch(() => {
          applyStatusResult(true)
        })
        .finally(() => {
          frontend.setBackendStatusRequest(null)
        })
    }
    return config
  }

  // Check if there's already a backend status request running. If yes, use it. If not, start one.
  if (frontend.backend_status_request === null) {
    frontend.setBackendStatusRequest(axios.get(frontend.backend_status_url, { timeout: 5000 }))
  }

  if (frontend.backend_status_request !== null) {
    // Backend status verification through /status endpoint should always return a 204 status-code.
    const backend_offline = await frontend.backend_status_request
      .then((response) => response.status !== 204)
      .catch(() => true)

    // Update backend status and reset status-request variable
    applyStatusResult(backend_offline)
    frontend.setBackendStatusRequest(null)

    if (backend_offline) {
      // Throw dedicated error so services can differentiate between offline backend and other kind of errors
      throw backend_offline_error
    }
  }
  return config
}, (error) => Promise.reject(error))

export default axios_backend_instance
