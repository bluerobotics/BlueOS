// three ships the same Draco decoder that GLTFLoader and <model-viewer> would otherwise
// fetch from a Google CDN, so we bundle it to keep 3D models loadable without internet access.
const decoderFiles = import.meta.glob(
  '/node_modules/three/examples/jsm/libs/draco/{draco_decoder.js,draco_decoder.wasm,draco_wasm_wrapper.js}',
  { eager: true, as: 'url' },
)

/**
 * URL of the directory serving the bundled Draco decoder, as expected by DRACOLoader's
 * decoder path. Returns undefined if the decoder was not bundled, in which case loaders
 * keep their default CDN location.
 */
export default function dracoDecoderPath(): string | undefined {
  const wasmFile = Object.keys(decoderFiles).find((key) => key.endsWith('draco_decoder.wasm'))
  if (wasmFile === undefined) {
    console.warn('Bundled Draco decoder not found, 3D models will only load with internet access.')
    return undefined
  }
  return decoderFiles[wasmFile].replace(/[^/]*$/, '')
}
