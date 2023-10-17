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

new Vue({
  router,
  store,
  vuetify,
  render: (h) => h(App),
}).$mount('#app')
