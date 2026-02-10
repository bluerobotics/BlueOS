<template>
  <v-app v-if="!full_page_requested" :class="app_style">
    <v-card
      id="context-menu"
      ref="contextMenu"
      :class="context_menu_class"
      :style="context_menu_style"
    >
      <v-list>
        <v-list-item-subtitle class="ml-2 mb-2 font-weight-bold">
          Widgets
        </v-list-item-subtitle>
        <v-checkbox
          v-for="(name, index) in topWidgetsName"
          :key="index"
          v-model="selected_widgets"
          :label="name"
          :value="name"
          class="pa-0 pl-3 ma-0"
          @change="settings.user_top_widgets = selected_widgets"
        />
      </v-list>
    </v-card>
    <v-card
      flat
    >
      <v-app-bar
        app
        rounded="0"
        :class="app_bar_style"
        :height="toolbar_height"
        @contextmenu.prevent="navBarHandler($event)"
      >
        <v-app-bar-nav-icon
          id="hamburguer-menu-button"
          :style="{ visibility: drawer ? 'hidden' : 'visible' }"
          color="white"
          @click="drawer = true"
        />
        <v-card
          v-if="!safe_mode"
          v-tooltip="'Some functionality is not available while the vehicle is armed'"
          class="d-flex align-center warning justify-center mr-5"
          height="40"
        >
          <v-icon class="ml-3">
            mdi-alert-outline
          </v-icon>
          <v-card-title>
            Armed
          </v-card-title>
        </v-card>
        <draggable v-model="selected_widgets" class="d-flex align-center justify-center">
          <component
            :is="getWidget(widget_name).component"
            v-for="(widget_name, i) in selected_widgets"
            :key="i"
            v-bind="getWidget(widget_name).props"
            class="mr-2"
            ripple
            disabled
          />
        </draggable>
        <v-spacer />
        <span class="d-flex flex-column align-center">
          <backend-status-checker @statusChange="changeBackendStatus" />
        </span>
        <v-spacer />
        <beacon-tray-menu />
        <health-tray-menu />
        <gps-tray-menu :instance="1" />
        <gps-tray-menu :instance="2" />
        <theme-tray-menu />
        <system-checker-tray-menu />
        <vehicle-reboot-required-tray-menu />
        <on-board-computer-required-tray-menu />
        <pirate-mode-tray-menu />
        <internet-tray-menu />
        <wifi-tray-menu />
        <ethernet-tray-menu />
        <cloud-tray-menu v-if="is_cloud_tray_menu_visible" />
        <notification-tray-button />
      </v-app-bar>
    </v-card>

    <v-navigation-drawer
      id="drawer"
      v-model="drawer"
      app
      fixed
      @input="drawerEvent"
    >
      <v-container
        elevation="0"
        class="d-flex justify-center align-center"
        style="cursor: pointer"
        @click="goHome"
      >
        <v-img
          alt="Blue Robotics Logo"
          class="shrink mr-2"
          contain
          :src="blueos_logo"
          width="70%"
        />
      </v-container>
      <v-divider />
      <v-container
        elevation="0"
        class="d-flex justify-center align-center pa-0"
      >
        <vehicle-banner />
      </v-container>

      <v-container
        class="pa-1"
      >
        <v-divider />
        <v-list
          v-for="(menu, i) in computed_menu"
          :key="i"
          class="pa-0"
          nav
          dense
        >
          <v-list-item-group color="primary">
            <v-list-group
              v-if="menu.submenus"
              :id="`button-to-${menu.title.toLowerCase().replace(' ', '-')}`"
              :prepend-icon="menu.icon"
              :to="menu.route"
              no-action
            >
              <template #activator>
                <v-list-item-title>
                  {{ menu.title }}
                  <v-chip
                    v-if="menu.beta"
                    class="ma-2 pl-2 pr-2"
                    color="red"
                    pill
                    x-small
                    text-color="white"
                  >
                    Beta
                  </v-chip>
                </v-list-item-title>
              </template>

              <template
                v-for="(submenu, j) in menu.submenus"
              >
                <v-list-item
                  v-if="!submenu.advanced || (submenu.advanced && settings.is_pirate_mode)"
                  :key="j"
                  :target="submenu?.new_page ? '_blank' : '_self'"
                  :to="submenu.route"
                  :href="menu.extension ? submenu.route : undefined"
                >
                  <v-list-item-icon style="min-width:28px;">
                    <v-img
                      v-if="submenu.icon.startsWith('http')"
                      class="shrink mr-0"
                      contain
                      :src="submenu.icon"
                      width="24"
                    />
                    <!-- eslint-disable vue/no-v-html -->
                    <v-img
                      v-else-if="submenu.icon.startsWith('<svg')"
                      width="24"
                      :class="svg_outside_style"
                      v-html="submenu.icon"
                    />
                    <v-icon
                      v-else
                      class="mr-0"
                      v-text="submenu.icon"
                    />
                    <v-theme-provider
                      v-if="submenu.advanced && settings.is_pirate_mode"
                      dark
                    >
                      <div
                        v-tooltip="'This is an advanced feature'"
                        class="pirate-marker ma-0"
                      >
                        <v-avatar
                          class="ma-0"
                          color="error"
                          size="15"
                        >
                          <v-icon
                            size="15"
                            v-text="'mdi-skull-crossbones'"
                          />
                        </v-avatar>
                      </div>
                    </v-theme-provider>
                  </v-list-item-icon>
                  <v-list-item-title
                    v-text="submenu.title"
                  />
                </v-list-item>
              </template>
            </v-list-group>

            <v-list-item
              v-else
              :id="`button-to-${menu.title.toLowerCase().replace(' ', '-')}`"
              :to="menu.new_page || menu.disabled ? null : menu.route"
              :target="menu.new_page ? '_blank' : '_self'"
              :href="menu.extension && !menu.disabled ? menu.route : undefined"
              :disabled="menu.disabled"
            >
              <template #default>
                <v-list-item-icon style="min-width:28px;">
                  <v-img
                    v-if="menu.icon.startsWith('http')"
                    class="shrink mr-0"
                    contain
                    :src="menu.icon"
                    width="24"
                  />
                  <!-- eslint-disable vue/no-v-html -->
                  <v-img
                    v-else-if="menu.icon.startsWith('<svg')"
                    width="24"
                    :class="svg_outside_style"
                    v-html="menu.icon"
                  />
                  <v-icon
                    v-else
                    class="mr-0"
                    v-text="menu.icon"
                  />
                  <v-theme-provider
                    v-if="menu.advanced && settings.is_pirate_mode"
                    dark
                  >
                    <div
                      v-tooltip="'This is an advanced feature'"
                      class="pirate-marker ma-0"
                    >
                      <v-avatar
                        class="ma-0"
                        color="error"
                        size="15"
                      >
                        <v-icon
                          size="15"
                          v-text="'mdi-skull-crossbones'"
                        />
                      </v-avatar>
                    </div>
                  </v-theme-provider>
                  <v-theme-provider
                    v-if="menu.disabled"
                    dark
                  >
                    <div
                      class="extension-marker ma-0"
                    >
                      <v-avatar
                        class="ma-0"
                        color="error"
                        size="15"
                      >
                        <v-icon
                          size="12"
                          v-text="'mdi-cloud-off'"
                        />
                      </v-avatar>
                    </div>
                  </v-theme-provider>
                  <v-theme-provider
                    v-else-if="menu.extension"
                    dark
                  >
                    <div
                      v-tooltip="'This is an installed extension'"
                      class="extension-marker ma-0"
                    >
                      <v-avatar
                        class="ma-0"
                        color="success"
                        size="15"
                      >
                        <v-icon
                          size="12"
                          v-text="'mdi-puzzle'"
                        />
                      </v-avatar>
                    </div>
                  </v-theme-provider>
                </v-list-item-icon>
                <v-list-item-title>
                  {{ menu.title }}
                  <v-chip
                    v-if="menu.beta"
                    class="ma-2 pl-2 pr-2"
                    color="red"
                    pill
                    x-small
                    text-color="white"
                  >
                    Beta
                  </v-chip>
                </v-list-item-title>
              </template>
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
          BlueOS Version:
          <a
            target="_blank"
            rel="noopener noreferrer"
            :href="git_info_url"
          >
            {{ git_info }}
          </a>
        </span>
        <span
          v-if="bootstrap_version"
          class="build_info"
        >
          Bootstrap Version: {{ bootstrap_version.split(':')[1] }}
        </span>
        <!-- eslint-disable vuejs-accessibility/click-events-have-key-events -->
        <span
          id="current-version"
          class="build_info"
          @click="buildDateClick"
        >
          Build: {{ build_date }}
          <v-btn
            v-if="settings.is_dev_mode"
            v-tooltip="'Disable dev mode'"
            icon
            @click.stop="bluePillClick"
          >
            <v-icon color="primary">
              mdi-pill
            </v-icon>
          </v-btn>
        </span>
        <span
          class="build_info"
        >
          By
          <a
            target="_blank"
            rel="noopener noreferrer"
            href="https://bluerobotics.com"
            style="text-decoration:none;"
          >
            Blue Robotics
          </a>
        </span>
      </v-container>
    </v-navigation-drawer>

    <v-main>
      <router-view />
      <div id="tour-center-hook" />
    </v-main>
    <ethernet-updater />
    <mavlink-updater />
    <new-version-notificator />
    <Wizard @start-tour="setStartTour" />
    <alerter />
    <VTour
      name="welcomeTour"
      :steps="steps.filter((step) => step?.filter_wifi_connected !== wifi_connected)"
      :callbacks="tourCallbacks"
    />
  </v-app>
  <div v-else>
    <router-view />
  </div>
</template>

<script lang="ts">
import stable from 'semver-stable'
import Vue, { defineAsyncComponent } from 'vue'

import blueos_blue from '@/assets/img/blueos-logo-blue.svg'
import blueos_white from '@/assets/img/blueos-logo-white.svg'
import consoleLogger from '@/libs/console-logger'
import settings from '@/libs/settings'
import helper from '@/store/helper'
import wifi from '@/store/wifi'
import { Service } from '@/types/helper'
import { convertGitDescribeToTag, convertGitDescribeToUrl } from '@/utils/helper_functions'
import updateTime from '@/utils/update_time'
import * as VCU from '@/utils/version_chooser'

import Alerter from './components/app/Alerter.vue'
import BackendStatusChecker from './components/app/BackendStatusChecker.vue'
import InternetTrayMenu from './components/app/InternetTrayMenu.vue'
import NewVersionNotificator from './components/app/NewVersionNotificator.vue'
import OnBoardComputerRequiredTrayMenu from './components/app/OnBoardComputerRequiredTrayMenu.vue'
import PiradeModeTrayMenu from './components/app/PirateModeTrayMenu.vue'
import PowerMenu from './components/app/PowerMenu.vue'
import ReportMenu from './components/app/ReportMenu.vue'
import SettingsMenu from './components/app/SettingsMenu.vue'
import SystemCheckerTrayMenu from './components/app/SystemCheckerTrayMenu.vue'
import ThemeTrayMenu from './components/app/ThemeTrayMenu.vue'
import VehicleBanner from './components/app/VehicleBanner.vue'
import VehicleRebootRequiredTrayMenu from './components/app/VehicleRebootRequiredTrayMenu.vue'
import BeaconTrayMenu from './components/beacon/BeaconTrayMenu.vue'
import CloudTrayMenu from './components/cloud/CloudTrayMenu.vue'
import EthernetTrayMenu from './components/ethernet/EthernetTrayMenu.vue'
import EthernetUpdater from './components/ethernet/EthernetUpdater.vue'
import GpsTrayMenu from './components/health/GpsTrayMenu.vue'
import HealthTrayMenu from './components/health/HealthTrayMenu.vue'
import MavlinkUpdater from './components/mavlink/MavlinkUpdater.vue'
import NotificationTrayButton from './components/notifications/TrayButton.vue'
import WifiTrayMenu from './components/wifi/WifiTrayMenu.vue'
import menus, { menuItem } from './menus'
import autopilot_data from './store/autopilot'
import system_information from './store/system-information'
import { TopBarWidget } from './types/common'
import Cpu from './widgets/Cpu.vue'
import Disk from './widgets/Disk.vue'
import Networking from './widgets/Networking.vue'

export default Vue.extend({
  name: 'App',

  components: {
    'beacon-tray-menu': BeaconTrayMenu,
    'internet-tray-menu': InternetTrayMenu,
    'notification-tray-button': NotificationTrayButton,
    'pirate-mode-tray-menu': PiradeModeTrayMenu,
    'theme-tray-menu': ThemeTrayMenu,
    'wifi-tray-menu': WifiTrayMenu,
    'ethernet-tray-menu': EthernetTrayMenu,
    'cloud-tray-menu': CloudTrayMenu,
    'ethernet-updater': EthernetUpdater,
    'health-tray-menu': HealthTrayMenu,
    'gps-tray-menu': GpsTrayMenu,
    'mavlink-updater': MavlinkUpdater,
    'power-menu': PowerMenu,
    'settings-menu': SettingsMenu,
    'report-menu': ReportMenu,
    'backend-status-checker': BackendStatusChecker,
    Alerter,
    'vehicle-banner': VehicleBanner,
    'new-version-notificator': NewVersionNotificator,
    SystemCheckerTrayMenu,
    VehicleRebootRequiredTrayMenu,
    OnBoardComputerRequiredTrayMenu,
    Wizard: defineAsyncComponent(() => import('@/components/wizard/Wizard.vue')),
  },

  data: () => ({
    settings,
    drawer: undefined as boolean|undefined,
    drawer_running_tour: false,
    backend_offline: false,
    menus,
    tourCallbacks: {}, // we are setting this up in mounted otherwise "this" can be undefined
    context_menu_position: [0, 0],
    context_menu_visible: false,

    selected_widgets: settings.user_top_widgets,
    bootstrap_version: undefined as string|undefined,
    build_clicks: 0,
    start_tour: false,
  }),
  computed: {
    widgets(): TopBarWidget[] {
      const widgets = [
        {
          component: Cpu,
          name: 'CPU',
          props: {},
        },
        {
          component: Disk,
          name: 'Disk',
          props: {},
        },
      ]
      // lets filter out docker, veth, and zerotier interfaces
      if (!system_information.system?.network) {
        return widgets
      }
      const extra_interfaces = system_information.system?.network?.filter(
        (iface) => !['docker', 'lo', 'veth'].some((prefix) => iface.name.startsWith(prefix)),
      )
      for (const iface of extra_interfaces) {
        widgets.push({
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          component: Networking as any,
          props: {
            interface: iface.name,
          },
          name: `${iface.name} Networking`,
        })
      }
      return widgets
    },
    settings_selected_widgets(): string[] {
      return settings.user_top_widgets
    },
    isBehindWebProxy(): boolean {
      return window.location.host.endsWith('.cloud')
    },
    topWidgetsName(): string[] {
      return this.widgets.map((item) => item.name)
    },
    context_menu_class(): string {
      return this.context_menu_visible ? 'visible' : ''
    },
    context_menu_style(): string {
      return `left: ${this.context_menu_position[0]}px; top: ${this.context_menu_position[1]}px;`
    },
    app_style(): string {
      return settings.is_dark_theme ? 'dark-background' : 'light-background'
    },
    app_bar_style(): string {
      return settings.is_dark_theme ? 'dark-background-glass' : 'light-background-glass'
    },
    safe_mode(): boolean {
      return autopilot_data.is_safe
    },
    wifi_connected(): boolean {
      return wifi.current_network != null
    },
    toolbar_height(): number {
      return 56
    },
    full_page_requested(): boolean {
      return this.$router.currentRoute.query.full_page === 'true'
    },
    svg_outside_style(): string {
      return `mr-0 ${settings.is_dark_theme ? 'outside-svg-dark' : 'outside-svg-light'}`
    },
    computed_menu(): menuItem[] {
      const foundExtensions = helper.services
        .filter((service: Service) : boolean => service.metadata !== null)
        .map((service: Service) => {
          const address = this.createExtensionAddress(service)
          return {
            title: service.metadata?.name ?? 'Service name',
            icon: service.metadata?.icon?.startsWith('/')
              ? `${address}${service.metadata.icon}`
              : service.metadata?.icon ?? 'mdi-puzzle',
            route: this.addExtraQuery(service.metadata?.route ?? address, service.metadata?.extra_query),
            new_page: service.metadata?.avoid_iframes ?? service.metadata?.new_page,
            advanced: false,
            text: service.metadata?.description ?? 'Service text',
            extension: true,
            disabled: this.isBehindWebProxy && !service.metadata?.works_in_relative_paths,
          }
        })

      const filteredDefaultMenu = this.menus.filter((menu) => !menu.advanced || settings.is_pirate_mode)

      const extensions: menuItem[] = [
        {
          title: 'Extensions',
          icon: 'mdi-puzzle',
          route: '/tools/extensions-manager',
          advanced: false,
          text: 'Manage BlueOS extensions',
        },
        ...foundExtensions,
      ] as menuItem[]

      return [...filteredDefaultMenu, ...extensions].sort((a, b) => a.title.localeCompare(b.title))
    },
    steps() {
      return [
        {
          target: '#tour-center-hook',
          header: {
            title: 'Welcome to BlueOS!',
          },
          content: `We are happy to have you navigating with us! BlueOS provides the
          necessary tools to configure your vehicle, check the system status and more.
          Follow this quick tour to get familiar with your brand new onboard system.`,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#tour-center-hook',
          content: 'Connect BlueOS to the internet to enable online functionalities.',
          filter_wifi_connected: true,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#wifi-tray-menu-button',
          content: 'You can do this by connecting to a wifi network...',
          filter_wifi_connected: true,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#ethernet-tray-menu-button',
          content: '..or connecting to a wired Ethernet connection (usually from a router).',
          filter_wifi_connected: true,
          params: {
            enableScrolling: false,
          },
        },
        {
          target: '#drawer',
          content: 'This is the main BlueOS menu. Here you can access all the running services and system utilities.',
          params: {
            enableScrolling: false,
            placement: 'right',
          },
          before: () => {
            // It's necessary to control the drawer tour event otherwise the internal state control will close it
            this.drawer_running_tour = true
            // We will open the drawer for the message
            this.drawer = true
          },
        },
        {
          target: '#button-to-vehicle-setup',
          content: `Under the Vehicle Setup menu you can check the status of your autopilot sensors
          and test PWM outputs.`,
          params: {
            enableScrolling: false,
            placement: 'right',
          },
        },
        {
          target: '#button-to-autopilot-firmware',
          content: 'Here you can update the firmware of your autopilot, upload custom firmware files, and more.',
          params: {
            enableScrolling: false,
            placement: 'right',
          },
        },
        {
          target: '#button-to-autopilot-parameters',
          content: 'Here you can view and modify the parameters of your autopilot.',
          params: {
            enableScrolling: false,
            placement: 'right',
          },
        },
        {
          target: '#button-to-log-browser',
          content: 'Here you can browse the logs of your autopilot and download them.',
          params: {
            enableScrolling: false,
            placement: 'right',
          },
        },
        {
          target: '#button-to-video-streams',
          content: 'Here you can manage your video streams and configure them to your liking.',
          params: {
            enableScrolling: false,
            placement: 'right',
          },
        },
        {
          target: '#button-to-system-information',
          content: 'Here you can check the status of your system, processes and network.',
          params: {
            enableScrolling: false,
            placement: 'right',
          },
        },
        {
          target: '#button-to-network-test',
          content: 'You can test the speed of your network connection to your vehicle here.',
          params: {
            enableScrolling: false,
            placement: 'right',
          },
        },
        {
          target: '#button-to-extensions',
          content: 'And if you need to install new extensions, you can do it here.',
          params: {
            enableScrolling: false,
            placement: 'right',
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
      return import.meta.env.VITE_APP_GIT_DESCRIBE
    },
    git_info_url(): string {
      return convertGitDescribeToUrl(import.meta.env.VITE_APP_GIT_DESCRIBE)
    },
    build_date(): string {
      return import.meta.env.VITE_BUILD_DATE
    },
    blueos_logo(): string {
      return settings.is_dark_theme ? blueos_white : blueos_blue
    },
    is_cloud_tray_menu_visible(): boolean {
      // Keep tray menu visible in everything except stable versions
      const tag = convertGitDescribeToTag(this.git_info)
      return !tag || !stable.is(tag) || settings.is_dev_mode
    },
  },

  watch: {
    $route() {
      // In an update process the page may not be the 'Main' page, check tour when page changes
      this.checkTour()
      // Env may not exist when running it with `bun vite`
      const project_name = process.env.PROJECT_NAME ?? 'BlueOS'
      if (this.$route.name === this.$router.options.routes!.first()!.name) {
        document.title = project_name
        return
      }

      document.title = `${this.$route.name} - ${project_name}`
    },
    settings_selected_widgets() {
      this.selected_widgets = this.settings_selected_widgets
    },
    start_tour() {
      this.checkTour()
    },
  },

  async mounted() {
    this.checkAddress()
    this.setupCallbacks()
    this.checkTour()
    updateTime()

    const body = document.querySelector('body')
    body?.addEventListener('click', (event) => {
      const target = event.target as HTMLElement
      if (target.offsetParent !== this.$refs.contextMenu) {
        this.context_menu_visible = false
      }
    })
    this.bootstrap_version = await VCU.loadBootstrapCurrentVersion()
  },

  beforeDestroy() {
    consoleLogger.cleanup().catch((error) => {
      console.error('Failed to cleanup console logger:', error)
    })
  },

  methods: {
    addExtraQuery(url: string, extra_queries?: string) {
      if (!extra_queries) {
        return url
      }
      // adds additional query parameters to a url
      const separator = url.includes('?') ? '&' : '?'
      return url + separator + extra_queries
    },
    getWidget(name: string) {
      return this.widgets.find((widget) => widget.name === name) || { component: null, props: {} }
    },
    navBarHandler(event: Event) {
      const { clientX: mouseX, clientY: mouseY } = event as MouseEvent
      this.context_menu_position = [mouseX, mouseY]
      this.context_menu_visible = true
    },
    checkAddress(): void {
      if (window.location.host.includes('companion.local')) {
        window.location.replace('http://blueos.local')
      }
    },
    createExtensionAddress(service: Service): string {
      if (service.metadata?.avoid_iframes) {
        const base_url = window.location.origin.split(':').slice(0, 2).join(':')
        return `${base_url}:${service.port}`
      }
      if (service.metadata?.works_in_relative_paths) {
        return `/extensionv2/${service.metadata.sanitized_name}/`
      }
      let address = `/extension/${service?.metadata?.sanitized_name}`
      if (service?.metadata?.new_page) {
        address += '?full_page=true'
      }
      return address
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
      if (this.$route.name === this.$router.options.routes!.first()!.name
        && this.start_tour) {
        settings.run_tour_version(2)
          .then(() => {
            this.start_tour = false
            this.$tours.welcomeTour.start()
          })
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
    goHome(): void {
      if (this.$router.currentRoute.path !== '/') {
        this.$router.push('/')
      }
    },
    buildDateClick(): void {
      this.build_clicks = (this.build_clicks + 1) % 5
      if (this.build_clicks === 0) {
        settings.is_dev_mode = true
      }
    },
    bluePillClick(): void {
      this.build_clicks = 0
      settings.is_dev_mode = false
    },
    setStartTour(value: boolean): void {
      this.start_tour = value
    },
  },
})
</script>

<style>
::-webkit-scrollbar {
  width: 5px;
}

::-webkit-scrollbar-track {
  box-shadow: inset 0 0 1px grey;
  background: var(--v-primary-darken2);
}

::-webkit-scrollbar-thumb {
  background: var(--v-primary-darken3);
  transition: visibility 2s;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--v-primary-base);
}
</style>

<style scoped>

.outside-svg-dark {
  filter: invert(100%) brightness(200%);
}

.outside-svg-light {
  filter: invert(45%) brightness(100%);
}

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

#current-version {
  user-select: none;
}

#tour-center-hook {
  position: absolute;
  top: 20%;
  left: 50%;
}

div.extension-marker {
  position: relative;
  top: -10px;
  right: 7px;
  width: 15px;
  height: 15px;
  opacity: 0.7;
}

div.pirate-marker {
  position: relative;
  top: -10px;
  right: 7px;
  width: 15px;
  height: 15px;
  opacity: 0.7;
}

div.pirate-marker.v-icon {
    font-size: 10px;
}

/* Align home side menu item */
.v-list--nav .v-list-item {
  padding: 0 8px;
}

.v-list-item {
  padding: 0 4px;
}

.v-application--is-ltr .v-list--dense.v-list--nav .v-list-group--no-action > .v-list-group__items > .v-list-item {
  padding-left: 32px;
}

#context-menu {
  position: fixed;
  z-index: 10000;
  width: 150px;
  border-radius: 5px;
  transform: scale(0);
  transform-origin: top left;
}

#context-menu.visible {
  transform: scale(1);
  transition: transform 200ms ease-in-out;
}
</style>

<style>
.v-list-group__header__append-icon {
  margin-left: 0px !important;
  min-width: 24px !important;
}

.light-background {
  background-color: var(--v-br_blue-base) !important;
  background-image: linear-gradient(160deg, var(--v-br_blue-base) 0%, var(--v-mariner_blue-base) 100%) !important;
}

.dark-background {
  background-color: var(--v-mariner_blue-base) !important;
  background-image: linear-gradient(160deg, var(--v-mariner_blue-base) 0%, var(--v-blue_whale-base) 100%) !important;
}

.light-background-glass {
  /*
    It's not possible for us to get the color as variables and set a transparency on it,
    so we use the colors directly
  */
  background-color: #2699D055 !important;
  background-image: linear-gradient(160deg, #2699D088 0%, #135DA388 100%) !important;
  backdrop-filter: blur(4.5px) !important;
  -webkit-backdrop-filter: blur(10px) !important;
}

.dark-background-glass {
  /*
    It's not possible for us to get the color as variables and set a transparency on it,
    so we use the colors directly
  */
  background-color: #135DA355 !important;
  background-image: linear-gradient(160deg, #135DA388 0%, #012F4688 100%) !important;
  backdrop-filter: blur(4.5px) !important;
  -webkit-backdrop-filter: blur(10px) !important;
}

/* Global style */
/* mdi-loading icon is being used ? Of course you want to rotate it! */
.mdi-loading {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* Fix v-stepper disappearing when the screen is small*/
.v-stepper__label {
  display: block !important;
}

html {
  overflow: auto
}
</style>
