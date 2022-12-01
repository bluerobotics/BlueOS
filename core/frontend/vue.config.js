/* eslint-disable */
const { PRIMARY } = require('./src/assets/colors/default')

process.env.VUE_APP_BUILD_DATE = new Date().toLocaleString()
const SERVER_ADDRESS = process.env.BLUEOS_ADDRESS ?? 'http://blueos.local/'

module.exports = {
  devServer: {
    proxy: {
      '^/status': {
        target: SERVER_ADDRESS,
      },
      '^/ardupilot-manager': {
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
  }
}
