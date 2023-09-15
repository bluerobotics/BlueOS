import './cosmos'
import '@/style/css/vuetify-global.css'
import '@/style/css/animations.css'
import 'vue-tour/dist/vue-tour.css'

import Vue from 'vue'
import VueApexCharts from 'vue-apexcharts'
import JsonViewer from 'vue-json-viewer'
import VueTooltipDirective from 'vue-tooltip-directive'
import VueTour from 'vue-tour'
import VueDraggable from 'vuedraggable'
import Vuetify from 'vuetify/lib'

import App from './App.vue'
import DefaultTooltip from './components/common/DefaultTooltip.vue'
import vuetify from './plugins/vuetify'
import router from './router'
import store from './store'

Vue.use(VueTooltipDirective, {
  component: DefaultTooltip,
})
Vue.use(VueApexCharts)
Vue.use(Vuetify)
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
