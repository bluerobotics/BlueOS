import Vue from 'vue'

import App from './App.vue'
import vuetify from './plugins/vuetify'
import router from './router'
import store from './store'

new Vue({
  router,
  store,
  vuetify,
  render: (h) => h(App),
}).$mount('#app')
