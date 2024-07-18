<template>
  <v-menu
    v-if="is_tray_visible"
    v-model="menu_opened"
    :close-on-content-click="false"
    nudge-left="370"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        id="cloud-tray-menu-button"
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
          class="px-1"
          color="white"
        >
          mdi-cloud
        </v-icon>
      </v-card>
    </template>
    <v-card
      elevation="1"
      width="370"
      min-height="300"
      max-height="50vh"
    >
      <v-container
        v-if="operation_in_progress"
        class="text-center fill-height d-flex flex-column justify-center align-center"
        style="height: 300px;"
      >
        <spinning-logo
          size="30%"
          :subtitle="operation_description"
        />
        <pull-progress
          :progress="pull_tracker?.pull_output ?? ''"
          :show="pull_show_modal"
          :download="pull_tracker?.download_percentage ?? 0"
          :extraction="pull_tracker?.extraction_percentage ?? 0"
          :statustext="pull_tracker?.overall_status ?? ''"
        />
      </v-container>
      <v-container
        v-else-if="operation_error_message"
        class="text-center fill-height d-flex flex-column justify-center align-center"
        style="height: 300px;"
      >
        <v-icon
          color="red"
          size="70"
        >
          mdi-alert-octagon
        </v-icon>
        <v-card-title>
          {{ operation_error_title }}
        </v-card-title>
        <v-card-subtitle class="pt-2">
          {{ operation_error_message }}
        </v-card-subtitle>
      </v-container>
      <v-container
        v-else-if="is_major_tom_installed"
        class="py-0 px-0"
      >
        <v-app-bar
          elevate-on-scroll
        >
          <v-toolbar-title>Cloud</v-toolbar-title>
          <v-spacer />
        </v-app-bar>

        <v-container
          class="text-center fill-height d-flex flex-column justify-center align-center mt-5"
        >
          <v-icon
            :color="is_token_set ? 'green' : 'yellow'"
            size="70"
          >
            {{ is_token_set ? 'mdi-weather-cloudy' : 'mdi-wrench' }}
          </v-icon>
          <v-card-title>
            {{ is_token_set ? 'Setup is complete!' : 'Lets connect your vehicle!' }}
          </v-card-title>
          <v-btn
            color="primary"
            elevation="3"
            class="mt-4"
            :href="is_token_set ? blueos_cloud_url : blueos_cloud_vehicles_url"
            target="_blank"
            rel="noopener noreferrer"
            @click="() => {}"
          >
            Go to BlueOS Cloud
          </v-btn>
          <v-container
            class="d-flex align-center py-0 my-0"
            style="height: 90px; width: auto;"
          >
            <v-card-subtitle
              v-if="!setting_token"
              class="token-link-text mt-2 pt-1 pb-1"
              @click="setting_token = true"
            >
              Click here if you {{ is_token_set ? 'want to change your token' : 'already have a token' }}
            </v-card-subtitle>
            <v-slide-x-reverse-transition>
              <v-text-field
                v-if="setting_token"
                v-model="token"
                label="Token"
                type="text"
                variant="outlined"
              >
                <template #append>
                  <v-btn
                    icon
                    @click="setMajorTomToken()"
                  >
                    <v-icon
                      color="primary"
                      size="30"
                    >
                      mdi-check-circle-outline
                    </v-icon>
                  </v-btn>
                </template>
              </v-text-field>
            </v-slide-x-reverse-transition>
          </v-container>
        </v-container>
      </v-container>
      <v-container
        v-else
        class="text-center fill-height d-flex flex-column justify-center align-center"
        style="height: 300px;"
      >
        <v-icon
          color="yellow"
          size="70"
        >
          mdi-link-off
        </v-icon>
        <v-card-title>
          Major Tom is not installed
        </v-card-title>
        <v-card-subtitle class="pt-2">
          To use the cloud features of the Ground Control you need to install it.
        </v-card-subtitle>
        <v-btn
          color="primary"
          elevation="3"
          class="mt-4"
          @click="installMajorTom"
        >
          Install Major Tom
        </v-btn>
      </v-container>
    </v-card>
  </v-menu>
</template>

<script lang="ts">
import axios from 'axios'
import { StatusCodes } from 'http-status-codes'
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import PullProgress from '@/components/utils/PullProgress.vue'
import bag from '@/store/bag'
import { InstalledExtensionData, RunningContainer } from '@/types/kraken'
import back_axios from '@/utils/api'
import PullTracker from '@/utils/pull_tracker'

const KRAKEN_API_URL = '/kraken/v1.0'

const MAJOR_TOM_CLOUD_URL = 'https://blueos.cloud/major_tom/install'

const MAJOR_TOM_EXTENSION_IDENTIFIER = 'blueos.major_tom'

const BLUEOS_CLOUD_URL = 'https://app.blueos.cloud'

const BLUEOS_CLOUD_JOIN_URL = `${BLUEOS_CLOUD_URL}/api/agent/join/`

const BLUEOS_CLOUD_VEHICLES_URL = `${BLUEOS_CLOUD_URL}/vehicle/register/`

export default Vue.extend({
  name: 'CloudTrayMenu',
  components: {
    SpinningLogo,
    PullProgress,
  },
  data() {
    return {
      token: '',
      bag_token: '',
      setting_token: false,
      menu_opened: false,
      operation_in_progress: false,
      operation_description: '',
      pull_tracker: null as PullTracker | null,
      pull_show_modal: false,
      operation_error_title: null as string | null,
      operation_error_message: null as string | null,
      installed_extensions: {} as Record<string, InstalledExtensionData>,
      running_containers: [] as RunningContainer[],
      once_opened: false,
    }
  },
  computed: {
    is_major_tom_installed(): boolean {
      return MAJOR_TOM_EXTENSION_IDENTIFIER in this.installed_extensions
    },
    is_major_tom_running(): boolean {
      const extension = this.installed_extensions[MAJOR_TOM_EXTENSION_IDENTIFIER]

      return this.running_containers.some(
        (container) => container.image === `${extension?.docker}:${extension?.tag}`,
      )
    },
    is_token_set(): boolean {
      return this.bag_token !== ''
    },
    blueos_cloud_url(): string {
      return BLUEOS_CLOUD_URL
    },
    blueos_cloud_vehicles_url(): string {
      return BLUEOS_CLOUD_VEHICLES_URL
    },
    is_major_tom_ready(): boolean {
      return this.is_major_tom_installed && this.is_major_tom_running
    },
    is_tray_visible(): boolean {
      return this.is_major_tom_ready || this.once_opened
    },
  },
  watch: {
    menu_opened(new_value: boolean) {
      if (new_value) {
        this.once_opened = true
        this.setUpTrayMenu()
      } else {
        setTimeout(() => {
          this.setting_token = false
          this.token = ''
        }, 200)
      }
    },
  },
  async mounted() {
    await this.setUpTrayMenu()
  },
  methods: {
    async setUpTrayMenu() {
      await this.fetchExtensions()
      await this.fetchMajorTomBagToken()

      if (!this.once_opened && !this.is_major_tom_ready) {
        setTimeout(() => {
          this.setUpTrayMenu()
        }, 5000)
      }
    },
    startOperation(message: string): void {
      this.operation_description = message
      this.operation_error_title = null
      this.operation_error_message = null
      this.pull_show_modal = false
      this.operation_in_progress = true
    },
    setOperationError(title: string, error: unknown): void {
      this.operation_error_title = title
      this.operation_error_message = String(error)
    },
    async fetchMajorTomData(): Promise<InstalledExtensionData> {
      const data = await axios.get(MAJOR_TOM_CLOUD_URL)

      return data.data as InstalledExtensionData
    },
    async fetchMajorTomBagToken(): Promise<void> {
      const tomData = await bag.getData('major_tom')

      this.bag_token = String(tomData?.token ?? '')
    },
    async fetchExtensions(): Promise<void> {
      if (this.operation_in_progress) {
        return
      }
      this.startOperation('Checking if Major Tom is installed...')

      try {
        const installed = await back_axios({
          method: 'get',
          url: `${KRAKEN_API_URL}/installed_extensions`,
          timeout: 10000,
        })
        this.installed_extensions = {}
        for (const extension of installed.data) {
          this.installed_extensions[extension.identifier] = extension
        }

        const running = await back_axios({
          method: 'get',
          url: `${KRAKEN_API_URL}/list_containers`,
          timeout: 10000,
        })
        this.running_containers = running.data
      } catch (error) {
        this.setOperationError('Failed to determine if Major Tom is installed.', error)
      }

      this.operation_in_progress = false
    },
    async installMajorTom(): Promise<void> {
      if (this.operation_in_progress) {
        return
      }
      this.startOperation('Installing Major Tom...')

      this.pull_tracker = new PullTracker(
        () => console.log('Major Tom Install Ready'),
        (error: string) => {
          this.setOperationError('Failed to install Major Tom.', error)
        },
      )

      try {
        const majorTomData = await this.fetchMajorTomData()

        this.pull_show_modal = true

        await back_axios({
          method: 'POST',
          url: `${KRAKEN_API_URL}/extension/install`,
          data: majorTomData,
          onDownloadProgress: (progressEvent) => {
            this.pull_tracker?.digestNewData(progressEvent)
          },
        })
      } catch (error) {
        this.setOperationError('Failed to install Major Tom.', error)
      }

      this.operation_in_progress = false
      this.pull_show_modal = false

      await this.fetchExtensions()
    },
    async isMajorTomTokenValid(token: string): Promise<boolean> {
      let isValid = false
      try {
        await axios.put(
          BLUEOS_CLOUD_JOIN_URL,
          {},
          {
            headers: {
              Authorization: `Token ${token}`,
            },
          },
        )
      } catch (error) {
        if (error.response && error.response.status === StatusCodes.BAD_REQUEST) {
          isValid = true
        }
      }
      return isValid
    },
    async setMajorTomToken() {
      if (this.operation_in_progress) {
        return
      }
      this.startOperation('Setting Major Tom token...')

      const isTokenValid = await this.isMajorTomTokenValid(this.token)

      if (isTokenValid) {
        try {
          const tomData = await bag.getData('major_tom')
          await bag.setData('major_tom', { ...tomData, token: this.token })

          await back_axios({
            url: `${KRAKEN_API_URL}/extension/restart`,
            method: 'POST',
            params: {
              extension_identifier: MAJOR_TOM_EXTENSION_IDENTIFIER,
            },
            timeout: 10000,
          })
        } catch (restart_error) {
          this.setOperationError('Failed to set Major Tom token.', restart_error)
        }
      } else {
        this.setOperationError(
          'Failed to set Major Tom token.',
          'Invalid token. Please try again with a valid token.',
        )
      }

      this.operation_in_progress = false
      this.pull_show_modal = false

      this.token = ''
      this.setting_token = false

      await this.fetchMajorTomBagToken()
    },
  },
})
</script>

<style scoped>
.token-link-text {
  cursor: pointer;
  text-decoration: underline;
}
</style>
