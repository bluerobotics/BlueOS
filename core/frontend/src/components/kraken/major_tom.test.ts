import axios from 'axios'
import {
  afterEach, expect, mock, spyOn, test,
// eslint-disable-next-line import/no-unresolved
} from 'bun:test'

interface Config {
  onDownloadProgress: (event: object) => void
}
let config: Config | undefined
mock.module('../../utils/api', () => ({
  default: (requestConfig: Config) => {
    config = requestConfig
    return Promise.resolve()
  },
}))
const { installOrUpdateMajorTom } = await import('../../utils/major_tom')

afterEach(() => {
  config = undefined
})

async function install(): Promise<object[]> {
  spyOn(axios, 'get').mockResolvedValue({ data: { identifier: 'blueos.major_tom', docker: 'd', tag: 't' } })
  const received: object[] = []
  await installOrUpdateMajorTom((progress) => received.push(progress))
  return received
}

test('hands the native ProgressEvent to the caller', async () => {
  const received = await install()
  const native = { target: { response: 'data' } }
  config?.onDownloadProgress({ event: native })
  expect(received).toEqual([{ event: native }])
})

test('falls back to the event itself when axios provides no `.event`', async () => {
  const received = await install()
  const native = { target: { response: 'data' } }
  config?.onDownloadProgress(native)
  expect(received).toEqual([{ event: native }])
})
