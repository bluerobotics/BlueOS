import axios, { AxiosInstance } from 'axios'

import frontend from '@/store/frontend'

const backend_offline_error = new Error('Backend is offline')
backend_offline_error.name = 'BackendOffline'
export { backend_offline_error }

const axios_backend_instance: AxiosInstance = axios.create()

axios_backend_instance.interceptors.request.use(async (config) => {
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
    frontend.setBackendOffline(backend_offline)
    frontend.setBackendStatusRequest(null)

    if (backend_offline) {
      // Throw dedicated error so services can differentiate between offline backend and other kind of errors
      throw backend_offline_error
    }
  }
  return config
}, (error) => Promise.reject(error))

export default axios_backend_instance
