// eslint-disable-next-line @typescript-eslint/no-var-requires
const { gitDescribeSync } = require('git-describe')

process.env.VUE_APP_GIT_DESCRIBE = gitDescribeSync().raw
process.env.VUE_APP_BUILD_DATE = JSON.stringify(new Date())

module.exports = {
  devServer: {
    proxy: {
      '^/ardupilot-manager': {
        target: 'http://companion.local/',
      },
      '^/bridget': {
        target: 'http://companion.local/',
      },
      '^/cable-guy': {
        target: 'http://companion.local/',
      },
      '^/commander': {
        target: 'http://companion.local/',
      },
      '^/docker': {
        target: 'http://companion.local/',
      },
      '^/file-browser': {
        target: 'http://companion.local/',
      },
      '^/helper': {
        target: 'http://companion.local/',
      },
      '^/nmea-injector': {
        target: 'http://companion.local/',
      },
      '^/logviewer': {
        target: 'http://companion.local/',
      },
      '^/mavlink2rest': {
        target: 'http://companion.local/',
      },
      '^/mavlink-camera-manager': {
        target: 'http://companion.local/',
      },
      '^/system-information': {
        target: 'http://companion.local/',
      },
      '^/terminal': {
        target: 'http://companion.local/',
      },
      '^/version-chooser': {
        target: 'http://companion.local/',
      },
      '^/wifi-manager': {
        target: 'http://companion.local/',
      },
    },
  },
  transpileDependencies: ['vuetify', 'vuex-module-decorators'],
  pwa: {
    name: 'Companion',
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
