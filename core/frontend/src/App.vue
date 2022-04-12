<template>
  <v-app>
    <v-card
      flat
    >
      <v-app-bar
        app
        rounded="0"
        :color="app_bar_color"
        :extended="extend_toolbar"
        extension-height="10"
      >
        <v-app-bar-nav-icon
          id="hamburguer-menu-button"
          :style="{visibility: drawer ? 'hidden' : 'visible'}"
          color="white"
          @click="drawer = true"
        />

        <v-spacer />
        <span class="d-flex flex-column align-center">
          <backend-status-checker @statusChange="changeBackendStatus" />
          <span v-if="settings.is_pirate_mode">
            <span class="hidden-sm-and-down">Ahoy matey! You're running</span>
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
          </span>
        </span>
        <v-spacer />

        <health-tray-menu />
        <wifi-tray-menu />
        <ethernet-tray-menu />
        <notification-tray-button />
      </v-app-bar>
    </v-card>

    <v-navigation-drawer
      v-model="drawer"
      app
      fixed
      @input="drawerEvent"
    >
      <v-container
        elevation="0"
        class="d-flex justify-center"
      >
        <v-img
          alt="Blue Robotics Logo"
          class="shrink mr-2"
          contain
          src="./assets/img/logo.svg"
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
              :id="'button-to-' + menu.title.toLowerCase()"
              :prepend-icon="menu.icon"
              :to="menu.route"
              no-action
            >
              <template #activator>
                <v-list-item-title v-text="menu.title" />
              </template>

              <template
                v-for="(submenu, j) in menu.submenus"
              >
                <v-list-item
                  v-if="!submenu.advanced || (submenu.advanced && settings.is_pirate_mode)"
                  :key="j"
                  :to="submenu.route"
                >
                  <v-list-item-icon>
                    <v-icon v-text="submenu.icon" />
                  </v-list-item-icon>
                  <v-list-item-title
                    v-text="submenu.title"
                  />
                </v-list-item>
              </template>
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
          <report-menu />
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
        <span
          id="current-version"
          class="build_info"
        >Build: {{ build_date }}</span>
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
    <nmea-injector-updater />
    <new-version-notificator />
    <error-message />
    <v-tour
      name="welcomeTour"
      :steps="steps"
      :callbacks="tourCallbacks"
    />
    <div id="tour-center-hook" />
  </v-app>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'
import { convertGitDescribeToUrl } from '@/utils/helper_functions.ts'
import updateTime from '@/utils/update_time.ts'

import BackendStatusChecker from './components/app/BackendStatusChecker.vue'
import ErrorMessage from './components/app/ErrorMessage.vue'
import NewVersionNotificator from './components/app/NewVersionNotificator.vue'
import PowerMenu from './components/app/PowerMenu.vue'
import ReportMenu from './components/app/ReportMenu.vue'
import SettingsMenu from './components/app/SettingsMenu.vue'
import AutopilotManagerUpdater from './components/autopilot/AutopilotManagerUpdater.vue'
import EthernetTrayMenu from './components/ethernet/EthernetTrayMenu.vue'
import EthernetUpdater from './components/ethernet/EthernetUpdater.vue'
import HealthTrayMenu from './components/health/HealthTrayMenu.vue'
import MavlinkUpdater from './components/mavlink/MavlinkUpdater.vue'
import NMEAInjectorUpdater from './components/nmea-injector/NMEAInjectorUpdater.vue'
import NotificationTrayButton from './components/notifications/TrayButton.vue'
import ServicesScanner from './components/scanner/servicesScanner.vue'
import WifiTrayMenu from './components/wifi/WifiTrayMenu.vue'
import WifiUpdater from './components/wifi/WifiUpdater.vue'
import menus from './menus'

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
    'power-menu': PowerMenu,
    'settings-menu': SettingsMenu,
    'report-menu': ReportMenu,
    'backend-status-checker': BackendStatusChecker,
    'error-message': ErrorMessage,
    'new-version-notificator': NewVersionNotificator,
  },

  data: () => ({
    settings,
    drawer: undefined as boolean|undefined,
    drawer_running_tour: false,
    backend_offline: false,
    menus,
    tourCallbacks: {}, // we are setting this up in mounted otherwise "this" can be undefined
  }),
  computed: {
    extend_toolbar(): boolean {
      return settings.is_pirate_mode && this.backend_offline
    },
    steps() {
      return [
        {
          target: '#tour-center-hook',
          header: {
            title: 'Welcome to BlueOS!',
          },
          content: `We are happy to have you navigating with us! Follow this quick tour guide to get familiar with
          your brand-new companion system.`,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#tour-center-hook',
          content: `As stated on our welcome card, one of the first things you should do on your first use of BlueOS
          is to connect it to the internet.`,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#wifi-tray-menu-button',
          content: 'You can do it by connecting to a wifi network...',
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#ethernet-tray-menu-button',
          content: '...or by connecting to a cable internet (usually from/to a router).',
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#hamburguer-menu-button',
          content: 'This is the main BlueOS menu. Here you can access all the running services and system utilities.',
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#button-to-vehicle',
          content: `Under the Vehicle menu, you can check the status of your autopilot, download logs from it,
          set up video streams and even update its firmware!`,
          before: () => {
            // It's necessary to control the drawer tour event otherwise the internal state control will close it
            this.drawer_running_tour = true
            // We will open the drawer for the message
            this.drawer = true
          },
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#button-to-tools',
          content: `Here you can find all kinds of tools to improve your BlueOS experience.
          There are system-diagnosis tools, like network-speed tester and others, all under the Tools menu.`,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#power-menu-button',
          content: 'Here you can safely shut down or restart the running computer.',
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#settings-menu-button',
          content: 'With the settings button, you can customize your BlueOS experience.',
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#feature-request-button',
          content: `Here you can get in touch with us, request new features, report bugs, interact with our
          community, and more!`,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#current-version',
          content: `You can check the version of BlueOS installed here. This version number is particularly important
          when looking for help.`,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#notifications-tray-menu-button',
          content: 'Last but not least, you can find any event related to your system under the notifications menu.',
          before: () => {
            // The close vent will happen after the next tick of the state control
            this.drawer_running_tour = false
          },
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#tour-center-hook',
          content: `That's it! Now we want you to enjoy your experience with BlueOS! Also, don't forget to get in touch
          if you need anything else to improve your journey! Happy exploring!`,
          params: {
            enableScrolling: false,
          },
        },
      ]
    },
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

  watch: {
    $route() {
      // In an update process the page may not be the 'Main' page, check tour when page changes
      this.checkTour()
    },
  },

  mounted() {
    this.checkAddress()
    this.setupCallbacks()
    this.checkTour()
    updateTime()
  },

  methods: {
    checkAddress(): void {
      if (window.location.host.includes('companion.local')) {
        window.location.replace('http://blueos.local')
      }
    },
    setupCallbacks(): void {
      this.tourCallbacks = {
        onSkip: this.skipTour,
        onStop: this.skipTour,
      }
    },
    skipTour(): void {
      this.drawer_running_tour = false
    },
    checkTour(): void {
      // Check the current page and tour version to be sure that we are in the correct place before starting
      if (this.$route.name === 'Main') {
        settings.run_tour_version(2)
          .then(() => this.$tours.welcomeTour.start())
          .catch((message) => console.log(message))
      }
    },
    drawerEvent(): void {
      // If we are inside the tour, let the drawer open, the function will be called by the drawer state control
      if (this.drawer_running_tour) {
        this.$nextTick(() => { this.drawer = true })
      }
    },
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

#tour-center-hook {
  position: absolute;
  top: 20%;
  left: 50%;
}

</style>
