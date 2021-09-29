<template>
  <v-app>
    <v-card
      flat
    >
      <v-app-bar
        color="#08c"
        rounded="0"
      >
        <v-app-bar-nav-icon
          color="white"
          @click="drawer = true"
        />

        <v-spacer />
        <health-tray-menu />
        <wifi-tray-menu />
        <ethernet-tray-menu />
        <notification-tray-button />
      </v-app-bar>
    </v-card>

    <v-navigation-drawer
      v-model="drawer"
      absolute
      temporary
    >
      <v-container
        elevation="0"
        class="d-flex justify-center"
      >
        <v-img
          alt="Blue Robotics Logo"
          class="shrink mr-2"
          contain
          src="./assets/logo.svg"
          width="60"
        />
      </v-container>

      <v-container
        class="pa-1"
      >
        <v-divider />
        <v-list
          v-for="(menu, i) in menus"
          :key="i"
          class="pa-0"
          nav
          dense
        >
          <v-list-item-group color="primary">
            <v-list-group
              v-if="menu.submenus"
              :prepend-icon="menu.icon"
              :to="menu.route"
              no-action
            >
              <template #activator>
                <v-list-item-title v-text="menu.title" />
              </template>

              <v-list-item
                v-for="(submenu, j) in menu.submenus"
                :key="j"
                :to="submenu.route"
              >
                <v-list-item-title
                  v-text="submenu.title"
                />
                <v-list-item-icon>
                  <v-icon v-text="submenu.icon" />
                </v-list-item-icon>
              </v-list-item>
            </v-list-group>

            <v-list-item
              v-else
              :to="menu.route"
            >
              <v-list-item-icon>
                <v-icon v-text="menu.icon" />
              </v-list-item-icon>

              <v-list-item-title v-text="menu.title" />
            </v-list-item>
          </v-list-item-group>
        </v-list>
      </v-container>
    </v-navigation-drawer>

    <v-main>
      <router-view />
    </v-main>
    <services-scanner />
    <autopilot-manager-updater />
    <ethernet-updater />
    <wifi-updater />
    <mavlink-updater />
    <bridget-updater />
  </v-app>
</template>

<script lang="ts">
import Vue from 'vue'

import AutopilotManagerUpdater from './components/autopilot/AutopilotManagerUpdater.vue'
import BridgetUpdater from './components/bridges/BridgetUpdater.vue'
import EthernetTrayMenu from './components/ethernet/EthernetTrayMenu.vue'
import EthernetUpdater from './components/ethernet/EthernetUpdater.vue'
import HealthTrayMenu from './components/health/HealthTrayMenu.vue'
import MavlinkUpdater from './components/mavlink/MavlinkUpdater.vue'
import NotificationTrayButton from './components/notifications/TrayButton.vue'
import ServicesScanner from './components/scanner/servicesScanner.vue'
import WifiTrayMenu from './components/wifi/WifiTrayMenu.vue'
import WifiUpdater from './components/wifi/WifiUpdater.vue'

export default Vue.extend({
  name: 'App',

  components: {
    'notification-tray-button': NotificationTrayButton,
    'services-scanner': ServicesScanner,
    'wifi-tray-menu': WifiTrayMenu,
    'wifi-updater': WifiUpdater,
    'ethernet-tray-menu': EthernetTrayMenu,
    'ethernet-updater': EthernetUpdater,
    'autopilot-manager-updater': AutopilotManagerUpdater,
    'health-tray-menu': HealthTrayMenu,
    'mavlink-updater': MavlinkUpdater,
    'bridget-updater': BridgetUpdater,
  },

  data: () => ({
    drawer: false,
    menus: [
      {
        title: 'Main',
        icon: 'mdi-home',
        route: '/',
      },
      {
        title: 'Autopilot',
        icon: 'mdi-submarine',
        submenus: [
          {
            title: 'General',
            icon: 'mdi-image-filter-center-focus-strong',
            route: '/autopilot/general',
          },
          {
            title: 'Firmware',
            icon: 'mdi-chip',
            route: '/firmware',
          },
          {
            title: 'Log Browser',
            icon: 'mdi-file-multiple',
            route: '/logs',
          },
          {
            title: 'Endpoints',
            icon: 'mdi-arrow-decision',
            route: '/endpoints',
          },
          {
            title: 'Video',
            icon: 'mdi-video-vintage',
            route: '/videomanager',
          },
        ],
      },
      {
        title: 'Tools',
        icon: 'mdi-hammer-screwdriver',
        submenus: [
          {
            title: 'Bridges',
            icon: 'mdi-bridge',
            route: '/bridges',
          },
          {
            title: 'Filebrowser',
            icon: 'mdi-file-tree',
            route: '/filebrowser',
          },
          {
            title: 'Terminal',
            icon: 'mdi-console',
            route: '/web-terminal',
          },
          {
            title: 'Version-chooser',
            icon: 'mdi-cellphone-arrow-down',
            route: '/version-chooser',
          },
        ],
      },
    ],
  }),
})
</script>

<style>
.active_menu {
  color: blue;
}
</style>
