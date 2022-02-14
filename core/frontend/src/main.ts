import Vue from 'vue'
import VueTooltipDirective from 'vue-tooltip-directive'

import App from './App.vue'
import DefaultTooltip from './components/common/DefaultTooltip.vue'
import vuetify from './plugins/vuetify'
import router from './router'
import store from './store'

new Vue({
  router,
  store,
  vuetify,
  render: (h) => h(App),
}).$mount('#app')

Vue.use(VueTooltipDirective, {
  component: DefaultTooltip,
})
