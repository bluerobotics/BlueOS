import './cosmos'

import Vue from 'vue'
import VueApexCharts from 'vue-apexcharts'
import JsonViewer from 'vue-json-viewer'
import VueTooltipDirective from 'vue-tooltip-directive'
import VueTour from 'vue-tour'
import VueDraggable from 'vuedraggable'

import App from './App.vue'
import DefaultTooltip from './components/common/DefaultTooltip.vue'
import vuetify from './plugins/vuetify'
import router from './router'
import store from './store'

require('@/assets/css/vuetify-global.css')
require('@/assets/css/animations.css')
require('vue-tour/dist/vue-tour.css')

Vue.use(VueTooltipDirective, {
  component: DefaultTooltip,
})
Vue.use(VueApexCharts)
Vue.use(VueTour)
Vue.use(JsonViewer)

Vue.component('Apexchart', VueApexCharts)
Vue.component('Draggable', VueDraggable)

new Vue({
  router,
  store,
  vuetify,
  render: (h) => h(App),
}).$mount('#app')
