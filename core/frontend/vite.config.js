import vue from '@vitejs/plugin-vue2'
import { VuetifyResolver } from 'unplugin-vue-components/resolvers'
import Components from 'unplugin-vue-components/vite'
import { defineConfig, loadEnv } from 'vite'
import { sentryVitePlugin } from "@sentry/vite-plugin";
import { VitePWA } from 'vite-plugin-pwa'
import wasm from "vite-plugin-wasm"
const { name } = require('./package.json')

process.env.PROJECT_NAME = name
process.env.VITE_BUILD_DATE = new Date().toLocaleString()
const DEFAULT_ADDRESS = 'http://blueos-avahi.local/'
const SERVER_ADDRESS = process.env.BLUEOS_ADDRESS ?? DEFAULT_ADDRESS

const path = require('path')
const assert = require('assert');

// TODO: check if it works with https once we have something that does
assert.ok(SERVER_ADDRESS.startsWith('http://'), 'SERVER_ADDRESS must start with http://');

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [
      vue(),
      wasm(),
      VitePWA({
        registerType: 'autoUpdate',
        devOptions: {
          enabled: true,
        },
        includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'masked-icon.svg'],
      }),
      Components({
        // generate `components.d.ts` global declarations
        // https://github.com/antfu/unplugin-vue-components#typescript
        dts: true,
        // auto import for directives
        directives: false,
        // resolvers for custom components
        resolvers: [
          // Vuetify
          VuetifyResolver(),
        ],
        // https://github.com/antfu/unplugin-vue-components#types-for-global-registered-components
        types: [
          {
            from: 'vue-router',
            names: ['RouterLink', 'RouterView'],
          },
        ],
        // Vue version of project.
        version: 2.7,
      }),
      sentryVitePlugin({
        authToken: process.env.SENTRY_AUTH_TOKEN,
        org: "blue-robotics-c7",
        project: "blueos",
      }),
      // Fix Draco imports in dev server
      {
        name: 'draco-dev-fix',
        apply: 'serve',
        configureServer(server) {
          server.middlewares.use((req, res, next) => {
            if (req.url?.includes('/node_modules/three/examples/jsm/libs/draco/')) {
              const fs = require('fs')
              const filePath = path.join(__dirname, req.url)
              if (fs.existsSync(filePath)) {
                const ext = path.extname(req.url)
                if (ext === '.wasm') res.setHeader('Content-Type', 'application/wasm')
                else if (ext === '.js') res.setHeader('Content-Type', 'application/javascript')
                res.end(fs.readFileSync(filePath))
                return
              }
            }
            next()
          })
        }
      },
      // Remove non-JSON files from ArduPilot parameter repository to reduce image size
      {
        name: 'cleanup-ardupilot-files',
        apply: 'build',
        closeBundle() {
          const fs = require('fs')
          const repoPath = path.resolve(__dirname, 'dist/assets/ArduPilot-Parameter-Repository')
          if (!fs.existsSync(repoPath)) return

          const removeNonJson = (dir) => {
            for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
              const fullPath = path.join(dir, entry.name)
              if (entry.isDirectory()) {
                removeNonJson(fullPath)
              } else if (!entry.name.endsWith('.json') && !entry.name.endsWith('.json.gz')) {
                fs.unlinkSync(fullPath)
              }
            }
          }
          removeNonJson(repoPath)
        }
      },
    ],
    assetsInclude: ['**/*.gif', '**/*.glb', '**/*.png', '**/*.svg', '**/*.msg', "**/three/examples/jsm/libs/draco/*"],
    resolve: {
      extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue'],
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      sourcemap: true,
      target: 'esnext',
      rollupOptions: {
        input: {
          main: path.resolve(__dirname, 'index.html'),
        },
        output: {
          assetFileNames: (assetInfo) => {
            // List of file patterns to excluded from hashing
            const noHashPatterns = [
              /ArduPilot-Parameter-Repository.*\.json$/,
              /three\/examples\/jsm\/libs\/draco\//
            ];

            if (assetInfo.name) {
              if (noHashPatterns.some(pattern => pattern.test(assetInfo.name))) {
                return `assets/[name][extname]`;
              }
            }
            return `assets/[name]-[hash][extname]`;
          }
        }
      },
    },
    define: {
      'process.env': {},
      __APP_ENV__: env.APP_ENV,
    },
    optimizeDeps: {
      exclude: ['@ffmpeg/ffmpeg', '@ffmpeg/util']
    },
    server: {
      port: 8080,
      fs: {
        allow: ['..', './node_modules']
      },
      proxy: {
        '^/status': {
          target: SERVER_ADDRESS,
        },
        '^/ardupilot-manager': {
          target: SERVER_ADDRESS,
        },
        '^/bag': {
          target: SERVER_ADDRESS,
        },
        '^/beacon': {
          target: SERVER_ADDRESS,
        },
        '^/bridget': {
          target: SERVER_ADDRESS,
        },
        '^/cable-guy': {
          target: SERVER_ADDRESS,
        },
        '^/commander': {
          target: SERVER_ADDRESS,
        },
        '^/disk-usage': {
          target: SERVER_ADDRESS,
        },
        '^/docker': {
          target: SERVER_ADDRESS,
        },
        '^/extensionv2': {
          target: SERVER_ADDRESS,
        },
        '^/file-browser': {
          target: SERVER_ADDRESS,
        },
        '^/helper': {
          target: SERVER_ADDRESS,
        },
        '^/upload': {
          target: SERVER_ADDRESS,
        },
        '^/kraken': {
          target: SERVER_ADDRESS,
          onProxyRes: (proxyRes, request, response) => {
            proxyRes.on('data', (data) => {
              response.write(data)
            })
            proxyRes.on('end', () => {
              response.end()
            })
          },
        },
        '^/nmea-injector': {
          target: SERVER_ADDRESS,
        },
        '^/logviewer': {
          target: SERVER_ADDRESS,
        },
        '^/mavlink': {
          target: SERVER_ADDRESS,
          changeOrigin: true,
          ws: true,
        },
        '^/mavlink2rest': {
          target: SERVER_ADDRESS,
          changeOrigin: true,
          ws: true,
        },
        '^/mavlink-camera-manager': {
          target: SERVER_ADDRESS,
        },
        '^/network-test': {
          target: SERVER_ADDRESS,
          changeOrigin: true,
          ws: true,
        },
        '^/ping': {
          target: SERVER_ADDRESS,
        },
        '^/recorder-extractor': {
          target: SERVER_ADDRESS,
        },
        '^/system-information': {
          target: SERVER_ADDRESS,
          changeOrigin: true,
          ws: true,
        },
        '^/terminal': {
          target: SERVER_ADDRESS,
          changeOrigin: true,
          ws: true,
        },
        '^/userdata': {
          target: SERVER_ADDRESS,
          changeOrigin: true,
        },
        '^/vehicles': {
          target: SERVER_ADDRESS,
        },
        '^/version-chooser': {
          target: SERVER_ADDRESS,
          changeOrigin: true,
          onProxyRes: (proxyRes, request, response) => {
            proxyRes.on('data', (data) => {
              response.write(data)
            })
            proxyRes.on('end', () => {
              response.end()
            })
          },
        },
        '^/wifi-manager': {
          target: SERVER_ADDRESS,
        },
        '^/zenoh': {
          target: SERVER_ADDRESS,
        },
        '^/zenoh-api': {
          target: SERVER_ADDRESS,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  }
})
