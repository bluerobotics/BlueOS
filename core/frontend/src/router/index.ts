import Vue from 'vue'
import VueRouter, { RouteConfig } from 'vue-router'

import Firmware from '../views/FirmwareView.vue'
import LogView from '../views/LogView.vue'
import Main from '../views/MainView.vue'

Vue.use(VueRouter)

const routes: Array<RouteConfig> = [
  {
    path: '/',
    name: 'Main',
    component: Main,
  },
  {
    path: '/firmware',
    name: 'Firmware',
    component: Firmware,
  },
  {
    path: '/logs',
    name: 'LogManager',
    component: LogView,
  },
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes,
})

export default router
