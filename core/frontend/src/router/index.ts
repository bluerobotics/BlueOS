import Vue from 'vue'
import VueRouter, { RouteConfig } from 'vue-router'

import Autopilot from '../views/Autopilot.vue'
import AvailableServicesView from '../views/AvailableServicesView.vue'
import BagEditorView from '../views/BagEditorView.vue'
import BridgesView from '../views/BridgesView.vue'
import Endpoint from '../views/EndpointView.vue'
import ExtensionManagerView from '../views/ExtensionManagerView.vue'
import ExtensionView from '../views/ExtensionView.vue'
import FileBrowserView from '../views/FileBrowserView.vue'
import LogView from '../views/LogView.vue'
import Main from '../views/MainView.vue'
import MavlinkInspectorView from '../views/MavlinkInspectorView.vue'
import NetworkTestView from '../views/NetworkTestView.vue'
import NMEAInjectorView from '../views/NMEAInjectorView.vue'
import PageNotFound from '../views/PageNotFound.vue'
import ParameterEditorView from '../views/ParameterEditorView.vue'
import Pings from '../views/Pings.vue'
import SystemInformationView from '../views/SystemInformationView.vue'
import TerminalView from '../views/TerminalView.vue'
import VehicleSetupView from '../views/VehicleSetupView.vue'
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
    path: '/vehicle/autopilot',
    name: 'Autopilot',
    component: Autopilot,
  },
  {
    path: '/vehicle/Setup',
    name: 'Vehicle Setup',
    component: VehicleSetupView,
  },
  {
    path: '/vehicle/pings',
    name: 'Pings',
    component: Pings,
  },
  {
    path: '/vehicle/logs',
    name: 'Log Browser',
    component: LogView,
  },
  {
    path: '/vehicle/endpoints',
    name: 'Endpoints',
    component: Endpoint,
  },
  {
    path: '/tools/file-browser',
    name: 'File Browser',
    component: FileBrowserView,
  },
  {
    path: '/tools/web-terminal',
    name: 'Terminal',
    component: TerminalView,
  },
  {
    path: '/tools/version-chooser',
    name: 'Version Chooser',
    component: VersionChooser,
  },
  {
    path: '/vehicle/video-manager',
    name: 'Video Manager',
    component: VideoManagerView,
  },
  {
    path: '/tools/bridges',
    name: 'Bridges',
    component: BridgesView,
  },
  {
    path: '/tools/nmea-injector',
    name: 'NMEA Injector',
    component: NMEAInjectorView,
  },
  {
    path: '/tools/available-services',
    name: 'Available Services',
    component: AvailableServicesView,
  },
  {
    path: '/tools/system-information',
    name: 'System Information',
    component: SystemInformationView,
  },
  {
    path: '/tools/mavlink-inspector',
    name: 'Mavlink Inspector',
    component: MavlinkInspectorView,
  },
  {
    path: '/tools/network-test',
    name: 'Network Test',
    component: NetworkTestView,
  },
  {
    path: '/tools/bag-editor',
    name: 'Bag editor',
    component: BagEditorView,
  },
  {
    path: '/extensions/:port',
    name: 'Extensions',
    component: ExtensionView,
  },
  {
    path: '/extension/:name/*',
    name: 'Named Extensions (wildcard)',
    component: ExtensionView,
  },
  {
    path: '/extension/:name',
    name: 'Named Extensions',
    component: ExtensionView,
  },
  {
    path: '/tools/extensions-manager',
    name: 'Extension Manager',
    component: ExtensionManagerView,
  },
  {
    path: '/vehicle/parameters',
    name: 'Parameter Editor',
    component: ParameterEditorView,
  },
  {
    path: '*',
    name: '404',
    component: PageNotFound,
  },
]

const router = new VueRouter({
  mode: 'history',
  base: import.meta.env.BASE_URL,
  routes,
})

export default router
