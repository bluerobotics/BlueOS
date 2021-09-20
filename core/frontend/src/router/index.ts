import Vue from 'vue'
import VueRouter, { RouteConfig } from 'vue-router'

import Endpoint from '../views/EndpointView.vue'
import FileBrowserView from '../views/FileBrowserView.vue'
import Firmware from '../views/FirmwareView.vue'
import LogView from '../views/LogView.vue'
import Main from '../views/MainView.vue'
import TerminalView from '../views/TerminalView.vue'
import VersionChooser from '../views/VersionChooser.vue'

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
  {
    path: '/endpoints',
    name: 'Endpoints',
    component: Endpoint,
  },
  {
    path: '/filebrowser',
    name: 'FileBrowser',
    component: FileBrowserView,
  },
  {
    path: '/web-terminal',
    name: 'Terminal',
    component: TerminalView,
  },
  {
    path: '/versionchooser',
    name: 'VersionChooser',
    component: VersionChooser,
  },
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes,
})

export default router
