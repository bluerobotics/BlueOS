import Vue from 'vue'
import VueRouter, { RouteConfig } from 'vue-router'

import AvailableServicesView from '../views/AvailableServicesView.vue'
import BridgesView from '../views/BridgesView.vue'
import Endpoint from '../views/EndpointView.vue'
import FileBrowserView from '../views/FileBrowserView.vue'
import GeneralAutopilot from '../views/GeneralAutopilot.vue'
import LogView from '../views/LogView.vue'
import Main from '../views/MainView.vue'
import MavlinkInspectorView from '../views/MavlinkInspectorView.vue'
import NetworkTestView from '../views/NetworkTestView.vue'
import NMEAInjectorView from '../views/NMEAInjectorView.vue'
import SystemInformationView from '../views/SystemInformationView.vue'
import TerminalView from '../views/TerminalView.vue'
import VersionChooser from '../views/VersionChooser.vue'
import VideoManagerView from '../views/VideoManagerView.vue'

Vue.use(VueRouter)

const routes: Array<RouteConfig> = [
  {
    path: '/',
    name: 'Main',
    component: Main,
  },
  {
    path: '/autopilot/general',
    name: 'GeneralAutopilot',
    component: GeneralAutopilot,
  },
  {
    path: '/autopilot/logs',
    name: 'LogManager',
    component: LogView,
  },
  {
    path: '/autopilot/endpoints',
    name: 'Endpoints',
    component: Endpoint,
  },
  {
    path: '/tools/file-browser',
    name: 'FileBrowser',
    component: FileBrowserView,
  },
  {
    path: '/tools/web-terminal',
    name: 'Terminal',
    component: TerminalView,
  },
  {
    path: '/tools/version-chooser',
    name: 'VersionChooser',
    component: VersionChooser,
  },
  {
    path: '/autopilot/video-manager',
    name: 'VideoManager',
    component: VideoManagerView,
  },
  {
    path: '/tools/bridges',
    name: 'Bridges',
    component: BridgesView,
  },
  {
    path: '/tools/nmea-injector',
    name: 'NMEAInjector',
    component: NMEAInjectorView,
  },
  {
    path: '/tools/available-services',
    name: 'Available Services',
    component: AvailableServicesView,
  },
  {
    path: '/tools/system-information',
    name: 'SystemInformation',
    component: SystemInformationView,
  },
  {
    path: '/tools/mavlink-inspector',
    name: 'MavlinkInspector',
    component: MavlinkInspectorView,
  },
  {
    path: '/tools/network-test',
    name: 'NetworkTest',
    component: NetworkTestView,
  },
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes,
})

export default router
