/* eslint-disable */
const { name } = require('./package.json')
const { PRIMARY } = require('./src/assets/colors/default')
const { StatusCodes } = require('http-status-codes')
const http = require('http')

process.env.PROJECT_NAME = name
process.env.VUE_APP_BUILD_DATE = new Date().toLocaleString()
const DEFAULT_ADDRESS = 'http://blueos.local/'
const SERVER_ADDRESS = process.env.BLUEOS_ADDRESS ?? DEFAULT_ADDRESS

module.exports = {
  devServer: {
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
      '^/docker': {
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
        selfHandleResponse: true,
        onProxyRes: (proxyRes, request, response) => {
          proxyRes.on('data', (data) => {
            response.write(data);
          });
          proxyRes.on('end', () => {
            response.end();
          });
        }
      },
      '^/nmea-injector': {
        target: SERVER_ADDRESS,
      },
      '^/logviewer': {
        target: SERVER_ADDRESS,
      },
      '^/mavlink2rest': {
        target: SERVER_ADDRESS,
      },
      '^/mavlink-camera-manager': {
        target: SERVER_ADDRESS,
      },
      '^/network-test': {
        target: SERVER_ADDRESS,
      },
      '^/ping': {
        target: SERVER_ADDRESS,
      },
      '^/system-information': {
        target: SERVER_ADDRESS,
      },
      '^/terminal': {
        target: SERVER_ADDRESS,
      },
      '^/userdata': {
        target: SERVER_ADDRESS,
      },
      '^/vehicles': {
        target: SERVER_ADDRESS,
      },
      '^/version-chooser': {
        target: SERVER_ADDRESS,
        selfHandleResponse: true,
        onProxyRes: (proxyRes, request, response) => {
          proxyRes.on('data', (data) => {
            response.write(data);
          });
          proxyRes.on('end', () => {
            response.end();
          });
        }
      },
      '^/wifi-manager': {
        target: SERVER_ADDRESS,
      },
    },
  },
  transpileDependencies: ['vuetify', 'vuex-module-decorators'],
  pwa: {
    name: 'BlueOS',
    themeColor: PRIMARY,
    appleMobileWebAppCapable: 'yes',
    appleMobileWebAppStatusBarStyle: 'white',
    manifestOptions: {
      background_color: '#FFFFFF',
    },
    iconPaths: {
      favicon32: 'img/icons/favicon-32x32.png',
      favicon16: 'img/icons/favicon-16x16.png',
      appleTouchIcon: 'img/icons/apple-touch-icon.png',
    },
  },
  chainWebpack: config => {
    config.module
      .rule('vue')
      .use('vue-loader')
      .tap(options => {
        options.compiler = require('vue-template-babel-compiler')
        return options
      })
      .end()
      .end()
      // Add 'glb' to image support. it is a 3d image after all...
      .rule('images')
      .test(/\.(png|jpe?g|gif|webp|avif|glb)(\?.*)?$/)
      .end()
      config.resolve.set('fallback', {
        util: require.resolve('util/'),
    })
  }
}

async function checkUrlReachable(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      if (res.statusCode >= StatusCodes.OK && res.statusCode < StatusCodes.BAD_REQUEST) {
        resolve({ reachable: true, statusCode: res.statusCode });
      } else {
        resolve({ reachable: false, statusCode: res.statusCode });
      }
    });

    req.on('error', (err) => {
      reject(err);
    });

    req.end();
  });
}

async function getBlueOSReachableAddress() {
  const promises = SEARCHABLE_MDNS_ADDRESS.map((url) => checkUrlReachable(url));
  const results = await Promise.allSettled(promises);

  const address = results
    .map((result, index) => result?.value?.reachable === true ? SEARCHABLE_MDNS_ADDRESS[index] : undefined)
    .filter((address) => address !== undefined)
    ?.[0]

  if (address) {
    // The new line is necessary to show the value while running yarn
    console.log(`Found BlueOS on: ${address}\n`)
  }

  return address
}
