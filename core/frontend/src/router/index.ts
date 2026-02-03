import { defineAsyncComponent } from 'vue'
import Vue from 'vue'
import VueRouter, { RouteConfig } from 'vue-router'

import ExtensionView from '../views/ExtensionView.vue'
import Main from '../views/MainView.vue'
import PageNotFound from '../views/PageNotFound.vue'
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
    component: defineAsyncComponent(() => import('../views/Autopilot.vue')),
  },
  {
    path: '/vehicle/setup/:tab?/:subtab?',
    name: 'Vehicle Setup',
    component: defineAsyncComponent(() => import('../views/VehicleSetupView.vue')),
  },
  {
    path: '/vehicle/pings',
    name: 'Pings',
    component: defineAsyncComponent(() => import('../views/Pings.vue')),
  },
  {
    path: '/vehicle/logs',
    name: 'Log Browser',
    component: defineAsyncComponent(() => import('../views/LogView.vue')),
  },
  {
    path: '/vehicle/endpoints',
    name: 'Endpoints',
    component: defineAsyncComponent(() => import('../views/EndpointView.vue')),
  },
  {
    path: '/tools/file-browser/:path*',
    name: 'File Browser',
    component: defineAsyncComponent(() => import('../views/FileBrowserView.vue')),
  },
  {
    path: '/tools/disk',
    name: 'Disk',
    component: defineAsyncComponent(() => import('../views/Disk.vue')),
  },
  {
    path: '/tools/web-terminal',
    name: 'Terminal',
    component: defineAsyncComponent(() => import('../views/TerminalView.vue')),
  },
  {
    path: '/tools/version-chooser',
    name: 'Version Chooser',
    component: defineAsyncComponent(() => import('../views/VersionChooser.vue')),
  },
  {
    path: '/vehicle/video-manager',
    name: 'Video Manager',
    component: defineAsyncComponent(() => import('../views/VideoManagerView.vue')),
  },
  {
    path: '/tools/records',
    name: 'Records',
    component: defineAsyncComponent(() => import('../views/RecordsView.vue')),
  },
  {
    path: '/tools/bridges',
    name: 'Bridges',
    component: defineAsyncComponent(() => import('../views/BridgesView.vue')),
  },
  {
    path: '/tools/nmea-injector',
    name: 'NMEA Injector',
    component: defineAsyncComponent(() => import('../views/NMEAInjectorView.vue')),
  },
  {
    path: '/tools/available-services',
    name: 'Available Services',
    component: defineAsyncComponent(() => import('../views/AvailableServicesView.vue')),
  },
  {
    path: '/tools/system-information',
    name: 'System Information',
    component: defineAsyncComponent(() => import('../views/SystemInformationView.vue')),
  },
  {
    path: '/tools/mavlink-inspector',
    name: 'Mavlink Inspector',
    component: defineAsyncComponent(() => import('../views/MavlinkInspectorView.vue')),
  },
  {
    path: '/tools/network-test',
    name: 'Network Test',
    component: defineAsyncComponent(() => import('../views/NetworkTestView.vue')),
  },
  {
    path: '/tools/bag-editor',
    name: 'Bag editor',
    component: defineAsyncComponent(() => import('../views/BagEditorView.vue')),
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
    path: '/extensionv2/:name',
    name: 'Named Extensions (v2)',
    component: ExtensionView,
  },
  {
    path: '/tools/extensions-manager',
    name: 'Extension Manager',
    component: defineAsyncComponent(() => import('../views/ExtensionManagerView.vue')),
  },
  {
    path: '/vehicle/parameters',
    name: 'Parameter Editor',
    component: defineAsyncComponent(() => import('../views/ParameterEditorView.vue')),
  },
  {
    path: '/tools/zenoh-inspector',
    name: 'Zenoh Inspector',
    component: defineAsyncComponent(() => import('../views/ZenohInspectorView.vue')),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: defineAsyncComponent(() => import('../views/SettingsView.vue')),
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
