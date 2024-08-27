/// <reference types="vite/client" />
import './cosmos'
import '@/style/css/vuetify-global.css'
import '@/style/css/animations.css'
import './components/vue-tour/dist/vue-tour.css'

import Vue from 'vue'
import VueApexCharts from 'vue-apexcharts'
import JsonViewer from 'vue-json-viewer'
import VueTooltipDirective from 'vue-tooltip-directive'
import VueDraggable from 'vuedraggable'
import Vuetify from 'vuetify/lib'
import * as Sentry from "@sentry/vue";

import App from './App.vue'
import DefaultTooltip from './components/common/DefaultTooltip.vue'
import VStep from './components/vue-tour/src/components/VStep.vue'
import VTour from './components/vue-tour/src/components/VTour.vue'
import vuetify from './plugins/vuetify'
import router from './router'
import store from './store'

Vue.use(VueTooltipDirective, {
  component: DefaultTooltip,
})
Vue.use(VueApexCharts)
Vue.use(Vuetify)
Vue.use(JsonViewer)

Vue.component('Apexchart', VueApexCharts)
Vue.component('Draggable', VueDraggable)

// Do Vue-Tour registration manually
Vue.component('VTour', VTour)
Vue.component('VStep', VStep)
Vue.prototype.$tours = {}

const project = 'BlueOS'
// Avoid logging local development
const version = import.meta.env.VITE_APP_GIT_DESCRIBE
const isOfficialTag = version?.includes('tags/')
const release = `${project}@${version}`.replace('tags/', '').replace(/\//g, ':')
console.info(`Running: ${release}`)
if (version && isOfficialTag) {
  Sentry.init({
    Vue,
    release,
    dsn: 'https://d87285a04a74f71aac13445f60506708@o4507696465707008.ingest.us.sentry.io/4507765318615040',
    integrations: [
      Sentry.browserTracingIntegration({ router }),
      Sentry.replayIntegration(),
    ],
    tracesSampleRate: 1.0,
    tracePropagationTargets: [],
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    transport: Sentry.makeBrowserOfflineTransport(Sentry.makeFetchTransport),
  })
}

new Vue({
  router,
  store,
  vuetify,
  render: (h) => h(App),
}).$mount('#app')
