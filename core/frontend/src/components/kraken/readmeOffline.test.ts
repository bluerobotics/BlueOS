import axios, { AxiosRequestConfig } from 'axios'
import {
  afterAll, beforeAll, expect, test,
} from 'bun:test'

import frontend from '@/store/frontend'

import kraken from './KrakenManager'
import ReadmeLoader from './readmeLoader'

const requests: string[] = []
let rejectStatus: () => void
function release(): void {
  rejectStatus?.()
}
function adapter(config: AxiosRequestConfig): Promise<never> {
  requests.push(config.url ?? '')
  if (config.url === '/status') {
    return new Promise((_, reject) => { rejectStatus = () => reject(new Error('timeout of 5000ms exceeded')) })
  }
  return Promise.resolve({
    data: 'readme', status: 200, statusText: 'OK', headers: {}, config,
  } as never)
}
const defaultAdapter = axios.defaults.adapter
beforeAll(() => {
  axios.defaults.adapter = adapter
})
afterAll(() => {
  axios.defaults.adapter = defaultAdapter
})

test('a readme request that waits for a timed out /status check fails without being sent', async () => {
  const state = { readmes: {} as Record<string, string>, error: false }
  const loader = new ReadmeLoader({
    has: (key) => key in state.readmes,
    store: (key, readme) => { state.readmes[key] = readme },
    setLoading: () => undefined,
    setError: (error) => { state.error = error },
  })
  // Another caller (such as the major_tom polling) already started the shared /status check.
  frontend.setBackendStatusRequest(axios.get('/status', { timeout: 5000 }))
  const before = requests.length
  const loading = loader.load('a:1', () => kraken.fetchExtensionReadme('a', '1'))
  await new Promise((resolve) => { setTimeout(resolve, 10) })
  release()
  await loading

  expect(requests.slice(before)).toEqual([])
  expect(state.error).toBe(true)
})
