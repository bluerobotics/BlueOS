/**
 * Persists recording preview JPEGs across page loads.
 *
 * Keys include size and modification time so a repaired or replaced file does not keep showing the
 * picture of whatever was there before.
 */

const DB_NAME = 'blueos-recording-thumbnails'
const STORE_NAME = 'thumbnails'
const DB_VERSION = 1

export interface ThumbnailCacheKey {
  path: string
  sizeBytes: number
  modified: number
}

function keyOf({ path, sizeBytes, modified }: ThumbnailCacheKey): string {
  return `${path}:${sizeBytes}:${modified}`
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onerror = () => reject(request.error ?? new Error('Failed to open the thumbnail cache.'))
    request.onsuccess = () => resolve(request.result)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME)
      }
    }
  })
}

async function withStore<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDatabase()
  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, mode)
      const request = run(transaction.objectStore(STORE_NAME))
      request.onerror = () => reject(request.error ?? new Error('Thumbnail cache request failed.'))
      request.onsuccess = () => resolve(request.result)
    })
  } finally {
    database.close()
  }
}

export async function getCachedThumbnail(key: ThumbnailCacheKey): Promise<Blob | null> {
  if (typeof indexedDB === 'undefined') {
    return null
  }
  try {
    const value = await withStore('readonly', (store) => store.get(keyOf(key)))
    return value instanceof Blob ? value : null
  } catch {
    return null
  }
}

export async function setCachedThumbnail(key: ThumbnailCacheKey, blob: Blob): Promise<void> {
  if (typeof indexedDB === 'undefined') {
    return
  }
  try {
    await withStore('readwrite', (store) => store.put(blob, keyOf(key)))
  } catch {
    // A full disk or a private browsing mode without IndexedDB is not worth surfacing.
  }
}

export async function deleteCachedThumbnail(key: ThumbnailCacheKey): Promise<void> {
  if (typeof indexedDB === 'undefined') {
    return
  }
  try {
    await withStore('readwrite', (store) => store.delete(keyOf(key)))
  } catch {
    // Same as set: cache failures are silent.
  }
}
