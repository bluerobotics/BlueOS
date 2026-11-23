/// <reference types="vite/client" />
import './cosmos'
import '@/style/css/vuetify-global.css'
import '@/style/css/animations.css'
import './components/vue-tour/dist/vue-tour.css'
import '@/alerts'

import * as Sentry from "@sentry/vue";
import Vue from 'vue'
import VueApexCharts from 'vue-apexcharts'
import JsonViewer from 'vue-json-viewer'
import VueTooltipDirective from 'vue-tooltip-directive'
import VueDraggable from 'vuedraggable'
import Vuetify from 'vuetify/lib'

import consoleLogger from '@/libs/console-logger'
import { loadBlueosVersion, retryBlueosVersion } from '@/utils/blueos-version'
import { convertGitDescribeToTag } from '@/utils/helper_functions'

import DefaultTooltip from './components/common/DefaultTooltip.vue'
import VStep from './components/vue-tour/src/components/VStep.vue'
import VTour from './components/vue-tour/src/components/VTour.vue'
import i18n, { initI18n } from './i18n'
import vuetify from './plugins/vuetify'
import router from './router'
import store from './store'

Vue.use(VueTooltipDirective, {
  component: DefaultTooltip,
})
Vue.use(VueApexCharts)
Vue.use(Vuetify)
Vue.use(i18n)
Vue.use(JsonViewer)

Vue.component('Apexchart', VueApexCharts)
Vue.component('Draggable', VueDraggable)

// Do Vue-Tour registration manually
Vue.component('VTour', VTour)
Vue.component('VStep', VStep)
Vue.prototype.$tours = {}

// Nginx may still be starting when the first read fails, so the first retries are quick. The tail holds steady
// because a slow Pi under boot load needs time, not more attempts, and each read is capped by FETCH_TIMEOUT_MS
// (utils/blueos-version). Nothing waits for the version: mount does not depend on it, and a later success updates
// Sentry and the drawer.
const VERSION_RETRY_DELAYS_MS = [2000, 5000, 10000, 10000, 10000]

function initSentry(version: string): void {
  if (!version) {
    return
  }
  const release = `BlueOS@${version}`
  console.info(`Running: ${release}`)
  // Distance 0 is a build of the tag itself. Later commits stay out of Sentry.
  if (!convertGitDescribeToTag(version)) {
    return
  }
  Sentry.init({
    Vue,
    release,
    dsn: 'https://d87285a04a74f71aac13445f60506708@o4507696465707008.ingest.us.sentry.io/4507765318615040',
    integrations: [
      Sentry.browserTracingIntegration({ router }),
      Sentry.replayIntegration(),
      Sentry.feedbackIntegration({ autoInject: false }),
    ],
    tracesSampleRate: 1.0,
    tracePropagationTargets: [],
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    transport: Sentry.makeBrowserOfflineTransport(Sentry.makeFetchTransport),
  })
}

async function start(): Promise<void> {
  consoleLogger.initialize().catch((error) => {
    console.error('Failed to initialize console logger:', error)
  })

  // Runs in the background: the drawer reads the version reactively and Sentry starts once it is known.
  loadBlueosVersion()
    .then((version) => {
      initSentry(version)
      return version ? undefined : retryBlueosVersion(VERSION_RETRY_DELAYS_MS, initSentry)
    })
    .catch((error) => console.error('Failed to load the BlueOS version:', error))

  await initI18n()

  const { default: App } = await import('./App.vue')
  new Vue({
    router,
    store,
    vuetify,
    render: (h) => h(App),
  }).$mount('#app')
}

start().catch((error) => console.error('Failed to start application:', error))
