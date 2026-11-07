import type { ModelViewerGlobalConfig } from '@google/model-viewer/lib/features/loading'

import dracoDecoderPath from '@/utils/draco'

let cachedSupport: boolean | undefined
let loadPromise: Promise<boolean> | undefined

function hasDOM(): boolean {
  return globalThis.window !== undefined && globalThis.document !== undefined
}

function canCreateWebGLContext(): boolean {
  if (!hasDOM()) {
    return false
  }
  try {
    const canvas = globalThis.document.createElement('canvas')
    const context = canvas.getContext('webgl') ?? canvas.getContext('experimental-webgl')
    return context !== null
  } catch (error) {
    console.warn('WebGL detection error:', error)
    return false
  }
}

export function canUseModelViewer(): boolean {
  cachedSupport ??= canCreateWebGLContext()
  return cachedSupport
}

// model-viewer reads this global when its first element is created, so it has to be set
// before the library is imported.
function configureDecoderLocation(): void {
  const decoderPath = dracoDecoderPath()
  if (decoderPath === undefined) {
    return
  }
  const scope = globalThis as unknown as { ModelViewerElement?: ModelViewerGlobalConfig }
  scope.ModelViewerElement = { ...scope.ModelViewerElement, dracoDecoderLocation: decoderPath }
}

export function ensureModelViewer(): Promise<boolean> {
  if (!canUseModelViewer()) {
    return Promise.resolve(false)
  }
  if (loadPromise === undefined) {
    configureDecoderLocation()
    loadPromise = import('@google/model-viewer/dist/model-viewer')
      .then(() => true)
      .catch((error) => {
        console.warn('Failed to load model-viewer, proceeding without 3D viewer.', error)
        return false
      })
  }
  return loadPromise
}
