process.env.VUE_APP_BUILD_DATE = new Date().toLocaleString()
const SERVER_ADDRESS = 'http://companion.local/'

module.exports = {
  devServer: {
    proxy: {
      '^/status': {
        target: SERVER_ADDRESS,
      },
      '^/ardupilot-manager': {
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
      '^/system-information': {
        target: SERVER_ADDRESS,
      },
      '^/terminal': {
        target: SERVER_ADDRESS,
      },
      '^/version-chooser': {
        target: SERVER_ADDRESS,
      },
      '^/wifi-manager': {
        target: SERVER_ADDRESS,
      },
    },
  },
  transpileDependencies: ['vuetify', 'vuex-module-decorators'],
  pwa: {
    name: 'BlueOS',
    themeColor: '#08c',
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
}
