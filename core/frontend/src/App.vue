<template>
  <v-app>
    <v-card
      flat
    >
      <v-app-bar
        rounded="0"
        :color="app_bar_color"
      >
        <v-app-bar-nav-icon
          color="white"
          @click="drawer = true"
        />

        <v-spacer />
        <div
          v-if="settings.is_pirate_mode"
        >
          Ahoy matey! You're running
          <v-icon>
            mdi-flag-variant
          </v-icon>
          <v-icon>
            mdi-skull-crossbones
          </v-icon>
          Pirate Mode
          <v-icon>
            mdi-skull-crossbones
          </v-icon>
          <v-icon>
            mdi-flag-variant
          </v-icon>
        </div>

        <backend-status-checker @statusChange="changeBackendStatus" />
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
        <v-divider />
        <v-container class="d-flex justify-center">
          <power-menu />
          <settings-menu />
        </v-container>
        <span
          class="build_info"
        >
          Version:
          <a
            target="_blank"
            rel="noopener noreferrer"
            :href="git_info_url"
          >
            {{ git_info }}
          </a>
        </span>
        <span class="build_info">Build: {{ build_date }}</span>
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
    <nmea-injector-updater />
    <error-message />
  </v-app>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'
import { convertGitDescribeToUrl } from '@/utils/helper_functions.ts'

import BackendStatusChecker from './components/app/BackendStatusChecker.vue'
import ErrorMessage from './components/app/ErrorMessage.vue'
import PowerMenu from './components/app/PowerMenu.vue'
import SettingsMenu from './components/app/SettingsMenu.vue'
import AutopilotManagerUpdater from './components/autopilot/AutopilotManagerUpdater.vue'
import BridgetUpdater from './components/bridges/BridgetUpdater.vue'
import EthernetTrayMenu from './components/ethernet/EthernetTrayMenu.vue'
import EthernetUpdater from './components/ethernet/EthernetUpdater.vue'
import HealthTrayMenu from './components/health/HealthTrayMenu.vue'
import MavlinkUpdater from './components/mavlink/MavlinkUpdater.vue'
import NMEAInjectorUpdater from './components/nmea-injector/NMEAInjectorUpdater.vue'
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
    'nmea-injector-updater': NMEAInjectorUpdater,
    'bridget-updater': BridgetUpdater,
    'power-menu': PowerMenu,
    'settings-menu': SettingsMenu,
    'backend-status-checker': BackendStatusChecker,
    'error-message': ErrorMessage,
  },

  data: () => ({
    settings,
    drawer: false,
    backend_offline: false,
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
            route: '/autopilot/firmware',
          },
          {
            title: 'Log Browser',
            icon: 'mdi-file-multiple',
            route: '/autopilot/logs',
          },
          {
            title: 'Endpoints',
            icon: 'mdi-arrow-decision',
            route: '/autopilot/endpoints',
          },
          {
            title: 'Video',
            icon: 'mdi-video-vintage',
            route: '/autopilot/videomanager',
          },
        ],
      },
      {
        title: 'Tools',
        icon: 'mdi-hammer-screwdriver',
        submenus: [
          {
            title: 'Available Services',
            icon: 'mdi-account-hard-hat',
            route: '/tools/available-services',
          },
          {
            title: 'Bridges',
            icon: 'mdi-bridge',
            route: '/tools/bridges',
          },
          {
            title: 'Filebrowser',
            icon: 'mdi-file-tree',
            route: '/tools/filebrowser',
          },
          {
            title: 'NMEA Injector',
            icon: 'mdi-map-marker',
            route: '/tools/nmea-injector',
          },
          {
            title: 'System information',
            icon: 'mdi-chart-pie',
            route: '/tools/system-information',
          },
          {
            title: 'Terminal',
            icon: 'mdi-console',
            route: '/tools/web-terminal',
          },
          {
            title: 'Version-chooser',
            icon: 'mdi-cellphone-arrow-down',
            route: '/tools/version-chooser',
          },
        ],
      },
    ],
  }),
  computed: {
    git_info(): string {
      return process.env.VUE_APP_GIT_DESCRIBE
    },
    git_info_url(): string {
      return convertGitDescribeToUrl(process.env.VUE_APP_GIT_DESCRIBE)
    },
    build_date(): string {
      return process.env.VUE_APP_BUILD_DATE
    },
    app_bar_color(): string {
      return this.backend_offline ? 'grey darken-1' : '#08c'
    },
  },
  methods: {
    changeBackendStatus(backend_offline: boolean): void {
      this.backend_offline = backend_offline
    },
  },
})
</script>

<style>
html {
  overflow-y: auto
}

.active_menu {
  color: blue;
}

span.build_info {
  font-size: 70%;
  margin-left: 30px;
  display: block;
}

</style>
