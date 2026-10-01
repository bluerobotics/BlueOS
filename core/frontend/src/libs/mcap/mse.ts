import { abortError } from './abort'

export function isMediaSourceSupported(): boolean {
  return typeof window !== 'undefined' && 'MediaSource' in window
}

export function waitForSourceOpen(mediaSource: MediaSource, signal?: AbortSignal): Promise<void> {
  if (mediaSource.readyState === 'open') {
    return Promise.resolve()
  }
  return new Promise((resolve, reject) => {
    function onAbort(): void {
      cleanup()
      reject(signal?.reason ?? abortError())
    }
    function onOpen(): void {
      cleanup()
      resolve()
    }
    function cleanup(): void {
      mediaSource.removeEventListener('sourceopen', onOpen)
      signal?.removeEventListener('abort', onAbort)
    }
    mediaSource.addEventListener('sourceopen', onOpen)
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

export function appendSourceBuffer(
  sourceBuffer: SourceBuffer,
  data: Uint8Array,
  signal?: AbortSignal,
  errorMessage = 'The browser refused the media.',
): Promise<void> {
  return new Promise((resolve, reject) => {
    function onAbort(): void {
      cleanup()
      reject(signal?.reason ?? abortError())
    }
    function onUpdate(): void {
      cleanup()
      resolve()
    }
    function onError(): void {
      cleanup()
      reject(new Error(errorMessage))
    }
    function cleanup(): void {
      sourceBuffer.removeEventListener('updateend', onUpdate)
      sourceBuffer.removeEventListener('error', onError)
      signal?.removeEventListener('abort', onAbort)
    }
    sourceBuffer.addEventListener('updateend', onUpdate)
    sourceBuffer.addEventListener('error', onError)
    signal?.addEventListener('abort', onAbort, { once: true })
    try {
      sourceBuffer.appendBuffer(data)
    } catch (error) {
      cleanup()
      reject(error)
    }
  })
}
