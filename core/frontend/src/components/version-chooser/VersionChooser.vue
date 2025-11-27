<template>
  <div>
    <v-col
      max-width="1000"
      class="mx-auto"
    >
      <v-dialog
        v-model="show_docker_login_dialog"
        max-width="450"
      >
        <DockerLogin
          @cancel="show_docker_login_dialog = false"
        />
      </v-dialog>
      <v-card
        v-if="!settings.is_pirate_mode"
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <v-alert
          border="top"
          colored-border
          type="info"
          elevation="2"
        >
          Turn on Pirate mode to view all available BlueOS versions, including previous installs
          stored onboard, as well as past and current stable, beta, and development releases
          downloadable from Blue Robotics.
        </v-alert>

        <h2>Current Version</h2>
        <version-card
          v-if="current_version"
          :image="current_version"
          :current="true"
          :last-modified="current_version.last_modified"
          :loading="loading_images"
          :up-to-date="!loading_images
            && !newStableAvailable() && !newBetaAvailable() && !updateIsAvailable(current_version)"
          :new-stable-available="newStableAvailable()"
          :new-beta-available="runningBeta() ? newBetaAvailable() : ''"
          :update-available="updateIsAvailable(current_version)"
          @apply="setVersion"
          @pull-and-apply="pullAndSetVersion"
        />
        <v-alert
          v-if="available_versions.error"

          color="red lighten-2"
          dark
        >
          {{ available_versions.error }}
        </v-alert>
      </v-card>

      <v-card
        v-if="settings.is_pirate_mode"
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <h2>Local Versions</h2>
        <version-card
          v-for="(image, index) in local_versions.result.local"
          :key="`${image.sha}-${index}-local`"
          :image="image"
          :updating="updating_bootstrap"
          :current="image.tag === current_version?.tag && image.repository === current_version?.repository"
          :bootstrap-version="bootstrap_version"
          :update-available="updateIsAvailable(image)"
          :all-images-loaded="all_images_loaded"
          :deleting="isBeingDeleted(image)"
          :enable-delete="local_versions.result.local.length > 2"
          @delete="deleteVersion"
          @apply="setVersion"
          @pull-and-apply="pullAndSetVersion"
          @update-bootstrap="updateBootstrap"
        />
        <spinning-logo
          v-if="local_versions.loading"
          size="15%"
          subtitle="Loading local images..."
        />
      </v-card>
      <v-card
        v-if="settings.is_pirate_mode"
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <div class="d-flex justify-space-between pb-3">
          <h2>Remote Versions</h2>
          <v-btn
            color="primary"
            @click="show_docker_login_dialog = true"
          >
            Docker Login
          </v-btn>
        </div>
        <v-form
          @submit.prevent="loadVersions()"
        >
          <v-text-field
            v-model="selected_image"
            name="BlueOS Remote Repository"
            label="Remote repository"
            :append-icon="selected_image != default_repository ? 'mdi-restore' : undefined"
            @click:append="selected_image = default_repository"
          />
        </v-form>
        <v-alert
          v-if="available_versions.error"

          color="red lighten-2"
          dark
        >
          {{ available_versions.error }}
        </v-alert>
        <spinning-logo
          v-if="loading_images"
          size="15%"
          subtitle="Loading remote images..."
        />
        <version-card
          v-for="(image, index) in paginatedComponents"
          v-else
          :key="`${image.sha}-${index}`"
          :image="image"
          :remote="true"
          :update-available="updateIsAvailable(image)"
          :show-pull-button="!imageIsAvailableLocally(image.sha)"
          @pull-and-apply="pullAndSetVersion"
        />
        <v-card-actions
          v-if="!loading_images"
          class="justify-center"
        >
          <v-pagination
            v-if="totalPages > 1"
            v-model="page"
            :length="totalPages"
          />
        </v-card-actions>
      </v-card>
    </v-col>
    <pull-progress
      :progress="pull_output"
      :show="show_pull_output"
      :download="download_percentage"
      :extraction="extraction_percentage"
      :statustext="status_text"
    />
    <v-card
      v-if="settings.is_pirate_mode"
      max-width="900"
      class="mx-auto pa-4"
    >
      <h2>Manual upload</h2>
      Use this to upload a .tar docker image. These can be downloaded from
      <a
        href="https://github.com/bluerobotics/BlueOS/actions/workflows/test-and-deploy.yml"
        target="_blank"
      >Github's CI</a>
      or generated locally using "docker save"
      <v-file-input
        v-if="!disable_upload_controls"
        id="file"
        show-size
        accept=".tar"
        :rules="[isFileInputNotEmpty]"
        :error-messages="file_input_error"
        label="File input"
      />
      <v-progress-linear
        v-if="disable_upload_controls && upload_percentage !== 100"
        class="mb-4 mt-4"
        :value="upload_percentage"
      />
      <v-btn
        v-if="!disable_upload_controls"
        color="primary"
        class="mr-2 mb-4 mt-1"
        @click="validateInputFileForm() && upload()"
        v-text="'Upload'"
      />

      <v-alert
        v-if="upload_percentage == 100"
        border="bottom"
        colored-border
        type="info"
        elevation="2"
      >
        Decompressing file, this usually takes up to one minute, please stand by...
        <spinning-logo
          v-if="upload_percentage == 100"
          size="15%"
          subtitle="Decompressing file..."
        />
      </v-alert>
    </v-card>
    <v-overlay
      :z-index="10"
      :value="waiting"
    >
      <spinning-logo
        size="100%"
        subtitle="Switching to new core..."
      />
    </v-overlay>
  </div>
</template>

<script lang="ts">
import { gt as sem_ver_greater, SemVer } from 'semver'
import Vue from 'vue'

import PullProgress from '@/components/utils/PullProgress.vue'
import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import helper from '@/store/helper'
import { version_chooser_service } from '@/types/frontend_services'
import { InternetConnectionState } from '@/types/helper'
import {
  isServerResponse,
  LocalVersionsQuery, Version, VersionsQuery, VersionType,
} from '@/types/version-chooser'
import back_axios from '@/utils/api'
import PullTracker from '@/utils/pull_tracker'
// Version Chooser Utils
import * as VCU from '@/utils/version_chooser'

import SpinningLogo from '../common/SpinningLogo.vue'
import DockerLogin from './DockerLogin.vue'
import VersionCard from './VersionCard.vue'

const notifier = new Notifier(version_chooser_service)

export default Vue.extend({
  name: 'VersionChooser',
  components: {
    DockerLogin,
    SpinningLogo,
    VersionCard,
    PullProgress,
  },
  data() {
    const default_repository = 'bluerobotics/blueos-core'
    return {
      settings,
      bootstrap_version: undefined as (undefined | string),
      pull_output: '',
      show_pull_output: false,
      page: 1,
      local_versions: {
        result: {
          local: [],
          error: null,
        } as LocalVersionsQuery,
        loading: false,
      },
      available_versions: {
        local: [],
        remote: [],
        error: null,
      } as VersionsQuery,
      latest_stable: undefined as (undefined | string),
      latest_beta: undefined as (undefined | string),
      disable_upload_controls: false,
      upload_percentage: 0,
      download_percentage: 0,
      extraction_percentage: 0,
      status_text: '',
      current_version: null as (null | Version),
      loading_images: false,
      updating_bootstrap: false,
      waiting: false,
      default_repository,
      selected_image: default_repository,
      deleting: '', // image currently being deleted, if any
      file_input_error: '',
      show_docker_login_dialog: false,
      all_images_loaded: false,
    }
  },
  computed: {
    paginatedComponents(): Version[] {
      return this.available_versions.remote.slice((this.page - 1) * 10, this.page * 10)
    },
    totalPages(): number {
      return Math.ceil(this.available_versions.remote.length / 10)
    },
    inputFileRequiredMessage(): string {
      return 'File is required'
    },
    has_internet(): boolean {
      return helper.has_internet !== InternetConnectionState.OFFLINE
    },
  },
  watch: {
    has_internet(value: boolean) {
      if (value) {
        this.loadAvailableVersions()
      } else {
        this.resetToNoInternetAvailable()
      }
    },
  },
  mounted() {
    this.loadCurrentVersion()
  },
  methods: {
    backendIsOnline() {
      return new Promise((resolve) => {
        back_axios({
          method: 'get',
          url: '/version-chooser/v1.0/version/current',
          timeout: 500,
        })
          .then(() => {
            resolve(true)
          })
          .catch(() => {
            resolve(false)
          })
      })
    },

    async waitForBackendToGoOffline() {
      let timeout = 0
      let interval = 0
      return new Promise((resolve, reject) => {
        timeout = setTimeout(
          () => {
            reject(new Error('backend took to long to shutdown!'))
            clearInterval(interval)
          },
          20000,
        )
        interval = setInterval(() => {
          this.backendIsOnline().then((backend_online) => {
            if (!backend_online) {
              clearTimeout(timeout)
              clearInterval(interval)
              resolve('backend went offline')
            }
          })
        }, 1000)
      })
    },

    waitForBackendToGoOnline() {
      let timeout = 0
      let interval = 0
      return new Promise((resolve, reject) => {
        timeout = setTimeout(
          () => {
            reject(new Error('backend took to long to come back'))
            clearInterval(interval)
          },
          120000,
        )
        interval = setInterval(() => {
          this.backendIsOnline().then((backend_online) => {
            if (backend_online) {
              clearTimeout(timeout)
              clearInterval(interval)
              resolve('backend went online')
            }
          })
        }, 1000)
      })
    },

    async waitForBackendToRestart(reload: boolean) {
      this.waiting = true
      try {
        await this.waitForBackendToGoOffline()
        await this.waitForBackendToGoOnline()
      } catch (e) {
        console.log('Backend took too long to restart')
      } finally {
        if (reload) {
          this.waiting = false
          window.location.reload()
        }
      }
    },

    runningBeta() {
      return VCU.getVersionType(this.current_version) === VersionType.Beta
    },
    newBetaAvailable() {
      if (!this.current_version) {
        return ''
      }
      if (this.latest_beta !== undefined && this.latest_beta !== this.current_version.tag) {
        return this.latest_beta
      }
      return ''
    },
    newStableAvailable() {
      if (!this.current_version || !VCU.isSemVer(this.current_version.tag)) {
        return ''
      }
      if (this.latest_stable !== undefined
        && sem_ver_greater(new SemVer(this.latest_stable), new SemVer(this.current_version.tag))) {
        return this.latest_stable
      }
      return ''
    },
    async loadLocalVersions() {
      this.local_versions.loading = true
      this.local_versions.result.local = []
      this.local_versions.result.error = null

      await VCU.loadLocalVersions()
        .then((versions_query) => {
          this.local_versions.loading = false
          this.local_versions.result = versions_query
        })
        .catch((error) => {
          this.local_versions.result = {
            local: [],
            error: `Failed to communicate with backend: ${error}`,
          }
        })
    },
    async loadAvailableVersions() {
      if (!this.has_internet) {
        this.resetToNoInternetAvailable()
        return
      }

      this.loading_images = true
      this.available_versions.error = null

      await VCU.loadAvailableVersions(this.selected_image)
        .then((versions_query) => {
          this.available_versions = versions_query
          this.all_images_loaded = true
        })
        .finally(() => {
          this.loading_images = false
          this.available_versions = VCU.sortImages(this.available_versions)
          this.latest_beta = VCU.getLatestBeta(this.available_versions)?.tag
          this.latest_stable = VCU.getLatestStable(this.available_versions)?.tag
        })
        .catch((error) => {
          this.all_images_loaded = false
          this.available_versions = {
            local: [],
            remote: [],
            error: `Failed to communicate with backend: ${error}`,
          }
        })
    },
    async loadVersions() {
      Promise.all([
        this.loadLocalVersions(),
        this.loadAvailableVersions(),
      ])
    },
    async loadCurrentVersion() {
      this.bootstrap_version = await VCU.loadBootstrapCurrentVersion()
      await VCU.loadCurrentVersion()
        .then((image) => {
          this.current_version = image
          this.selected_image = image.repository
          this.loadVersions()
        })
    },
    updateIsAvailable(image: Version) {
      const remote_counterpart = this.available_versions.remote.find(
        (remoteImage: Version) => remoteImage.tag === image.tag,
      )
      if (!remote_counterpart) {
        return false
      }
      return remote_counterpart.sha !== image.sha && remote_counterpart.sha !== null
    },
    async upload() {
      const file = this.getInputFile()
      if (file) {
        this.disable_upload_controls = true
        const formData = new FormData()
        formData.append('file', file)

        await back_axios({
          method: 'POST',
          url: '/version-chooser/v1.0/version/load',
          timeout: 15 * 60 * 1000, // Wait for 15min
          data: formData,
          onUploadProgress: (event) => {
            this.upload_percentage = Math.round(100 * (event.loaded / event.total))
          },
        }).finally(() => {
          this.disable_upload_controls = false
          this.upload_percentage = 0
          setTimeout(() => { this.loadVersions() }, 1000)
        })
      }
    },
    async pullAndSetVersion(args: string | string[]) {
      const fullname: string = Array.isArray(args) ? args[0] : args
      // This streams the output of docker pull
      this.pull_output = 'Fetching remote image...'
      this.show_pull_output = true
      await this.pullVersion(fullname)
        .then(() => {
          this.show_pull_output = false
          this.setVersion(fullname)
        })
        .catch((error) => {
          this.show_pull_output = false
          notifier.pushError(
            'VERSION_CHOOSER_PULL_FAIL',
            `The operation failed: ${error}`,
            true,
          )
        })
    },
    async pullVersion(image: string) {
      // This streams the output of docker pull
      this.pull_output = 'Fetching remote image...'
      this.show_pull_output = true
      const [repository, tag] = image.split(':')
      return new Promise<void>((resolve, reject) => {
        const tracker = new PullTracker(
          () => {
            setTimeout(() => {
              this.show_pull_output = false
              resolve()
            }, 1000)
          },
          (error) => {
            this.show_pull_output = false
            reject(error)
          },
        )

        back_axios({
          url: '/version-chooser/v1.0/version/pull/',
          method: 'POST',
          data: {
            repository,
            tag,
          },
          onDownloadProgress: (progressEvent) => {
            tracker.digestNewData(progressEvent.event, false)
            this.pull_output = tracker.pull_output
            this.download_percentage = tracker.download_percentage
            this.extraction_percentage = tracker.extraction_percentage
            this.status_text = tracker.overall_status
            this.show_pull_output = true
          },
        }).then((response) => {
          if (response.data.error) {
            reject(response.data.error)
          }
          this.show_pull_output = false
          resolve()
        })
      })
    },
    async updateBootstrap(image: string) {
      const [_, tag] = image.split(':')
      this.updating_bootstrap = true
      await this.pullVersion(image)
        .then(() => {
          this.show_pull_output = false
          this.setBootstrapVersion(tag)
        })
        .catch((error) => {
          this.show_pull_output = false
          notifier.pushError(
            'BOOTSTRAP_UPDATE_FAIL',
            `The operation failed: ${error}`,
            true,
          )
        })
      this.updating_bootstrap = false
    },
    async setBootstrapVersion(version: string, reload = true) {
      await back_axios({
        method: 'post',
        url: '/version-chooser/v1.0/bootstrap/current',
        data: {
          tag: version,
        },
      }).then((response) => {
        const { data } = response
        if (isServerResponse(data) && data.status !== 200) {
          notifier.pushError(
            'VERSION_CHOOSER_BOOTSTRAP_SET_FAIL',
            `The operation failed: ${data.title}, ${data.detail} (${data.status})`,
            true,
          )
          return
        }
        notifier.pushSuccess(
          'VERSION_CHOOSER_BOOTSTRAP_SET_SUCCESS',
          `Successfully updated bootstrap version to ${version}`,
          true,
        )
        if (reload) {
          window.location.reload()
        }
      })
    },
    async setVersion(args: string | string[]) {
      const fullname: string = Array.isArray(args) ? args[0] : args
      const [repository, tag] = fullname.split(':')

      if (this.isStable(tag)) {
        await this.setBootstrapVersion(tag, false)
      }

      await back_axios({
        method: 'post',
        url: '/version-chooser/v1.0/version/current',
        data: {
          repository,
          tag,
        },
      }).finally(() => { this.waitForBackendToRestart(true) })
    },
    async deleteVersion(args: string | string[]) {
      const fullname: string = Array.isArray(args) ? args[0] : args
      if (this.deleting === fullname) {
        return
      }
      const [repository, tag] = fullname.split(':')
      this.deleting = fullname
      await back_axios({
        method: 'delete',
        url: '/version-chooser/v1.0/version/delete',
        data: {
          repository,
          tag,
        },
      }).then(() => {
        // Remove this image in the frontend, as calling loadVersions()
        // takes a longer time to fetch all images
        this.local_versions.result.local = this.local_versions.result.local.filter(
          (element) => element.repository !== repository || element.tag !== tag,
        )
      })
        .catch((error) => { alert(error.response?.data ?? error.message) })
        .finally(() => { this.deleting = '' })
    },
    imageIsAvailableLocally(sha: string) : boolean {
      if (!('local' in this.available_versions)) {
        return false
      }
      return this.available_versions.local.some((image) => image.sha === sha)
    },
    getInputFile(): File | undefined {
      const { files } = document.getElementById('file') as HTMLInputElement

      return files?.[0]
    },
    isFileInputNotEmpty(v: File | null): true | string {
      this.file_input_error = ''
      return !!v || this.inputFileRequiredMessage
    },
    validateInputFileForm(): boolean {
      const valid = this.getInputFile() != null

      if (!valid) {
        this.file_input_error = this.inputFileRequiredMessage
      }

      return valid
    },
    resetToNoInternetAvailable() {
      this.available_versions = {
        ...this.available_versions,
        remote: [],
        error: "No internet connection available, can't fetch remote images",
      }
      this.latest_stable = undefined
      this.latest_beta = undefined
    },
    isBeingDeleted(image: Version) {
      return this.deleting === `${image.repository}:${image.tag}`
    },
    isStable(tag: string) {
      return VCU.isSemVer(tag) && !tag.includes('beta')
    },
  },
})
</script>
