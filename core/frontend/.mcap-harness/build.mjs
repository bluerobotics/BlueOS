import * as esbuild from 'esbuild'
import path from 'path'
import { fileURLToPath } from 'url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const codecData = path.join(root, 'node_modules/mediabunny/dist/modules/src/codec-data.js')
const entry = process.argv[2] ?? path.join(root, '.mcap-harness/harness.ts')
const outfile = process.argv[3] ?? path.join(root, '.mcap-harness/harness.js')

await esbuild.build({
  entryPoints: [entry],
  bundle: true,
  platform: 'node',
  outfile,
  plugins: [{
    name: 'mediabunny-codec-data',
    setup(build) {
      build.onResolve({ filter: /^mediabunny\/codec-data$/ }, () => ({ path: codecData }))
    },
  }],
})
