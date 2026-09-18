/** AbortError whose `name` matches what `AbortSignal` and `fetch` throw. */
export function abortError(message = 'The operation was cancelled.'): Error {
  const error = new Error(message)
  error.name = 'AbortError'
  return error
}

export function throwIfAborted(signal?: AbortSignal, message?: string): void {
  if (signal?.aborted) {
    throw abortError(message)
  }
}

/** Rejects with AbortError if `signal` fires while `work` is still pending. */
export function whileWaiting<T>(work: Promise<T>, signal?: AbortSignal, message?: string): Promise<T> {
  if (!signal) {
    return work
  }
  if (signal.aborted) {
    return Promise.reject(abortError(message))
  }
  return new Promise<T>((resolve, reject) => {
    function onAbort(): void {
      reject(abortError(message))
    }
    signal.addEventListener('abort', onAbort, { once: true })
    work.then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort))
  })
}

export function sleep(milliseconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError())
      return
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, milliseconds)
    function onAbort(): void {
      clearTimeout(timer)
      reject(abortError())
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}
