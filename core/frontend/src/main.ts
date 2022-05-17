import './cosmos'

import Vue from 'vue'
import VueTooltipDirective from 'vue-tooltip-directive'
import VueTour from 'vue-tour'

import App from './App.vue'
import DefaultTooltip from './components/common/DefaultTooltip.vue'
import vuetify from './plugins/vuetify'
import router from './router'
import store from './store'

require('@/assets/css/vuetify-global.css')
require('vue-tour/dist/vue-tour.css')

Vue.use(VueTooltipDirective, {
  component: DefaultTooltip,
})
Vue.use(VueTour)

new Vue({
  router,
  store,
  vuetify,
  render: (h) => h(App),
}).$mount('#app')
