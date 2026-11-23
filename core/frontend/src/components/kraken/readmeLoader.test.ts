import { expect, test } from 'bun:test'

import ReadmeLoader from './readmeLoader'

interface Deferred {
  resolve: (readme: string) => void
  reject: () => void
  promise: Promise<string>
}

function deferred(): Deferred {
  const result = {} as Deferred
  result.promise = new Promise<string>((resolve, reject) => {
    result.resolve = resolve
    result.reject = reject
  })
  return result
}

interface State {
  readmes: Record<string, string>
  loading: boolean
  error: boolean
}

function setup(): { state: State, loader: ReadmeLoader } {
  const state: State = { readmes: {}, loading: false, error: false }
  const loader = new ReadmeLoader({
    has: (key) => key in state.readmes,
    store: (key, readme) => { state.readmes[key] = readme },
    setLoading: (loading) => { state.loading = loading },
    setError: (error) => { state.error = error },
  })
  return { state, loader }
}

test('late failure of an earlier request for the same version does not show an error', async () => {
  const { state, loader } = setup()
  const firstA = deferred()
  const secondA = deferred()

  const loadingFirstA = loader.load('a:1', () => firstA.promise)
  const loadingB = loader.load('b:1', () => Promise.resolve('readme b'))
  const loadingSecondA = loader.load('a:1', () => secondA.promise)
  await loadingB

  secondA.resolve('readme a')
  await loadingSecondA
  firstA.reject()
  await loadingFirstA

  expect(state.error).toBe(false)
  expect(state.loading).toBe(false)
  expect(state.readmes['a:1']).toBe('readme a')
})

test('a failure of the latest request shows an error', async () => {
  const { state, loader } = setup()
  await loader.load('a:1', () => Promise.reject(new Error('timeout')))

  expect(state.error).toBe(true)
  expect(state.loading).toBe(false)
  expect(state.readmes['a:1']).toBeUndefined()
})

test('a cached readme is not fetched again', async () => {
  const { state, loader } = setup()
  let calls = 0
  async function fetcher(): Promise<string> {
    calls += 1
    return 'readme a'
  }
  await loader.load('a:1', fetcher)
  await loader.load('a:1', fetcher)

  expect(calls).toBe(1)
  expect(state.readmes['a:1']).toBe('readme a')
})

test('the same version is fetched again after a failure', async () => {
  const { state, loader } = setup()
  await loader.load('a:1', () => Promise.reject(new Error('backend offline')))
  expect(state.error).toBe(true)

  await loader.load('a:1', () => Promise.resolve('readme a'))
  expect(state.error).toBe(false)
  expect(state.readmes['a:1']).toBe('readme a')
})
