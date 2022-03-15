<template>
  <div>
    <v-col
      max-width="1000"
      class="mx-auto"
    >
      <v-card
        v-if="!settings.is_pirate_mode"
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <h2>Current Version</h2>
        <v-list
          subheader
          two-line
        >
          <version-card
            v-if="current_version"
            :image="current_version"
            :current="true"
            :last-modified="current_version.last_modified"
            :loading="loading_images"
            :up-to-date="!loading_images &&
              !newStableAvailable() && !newBetaAvailable() && !updateIsAvailable(current_version)"
            :new-stable-available="newStableAvailable()"
            :new-beta-available="runningBeta() ? newBetaAvailable() : ''"
            :update-available="updateIsAvailable(current_version)"
            @apply="setVersion"
            @pull-and-apply="pullAndSetVersion"
          />
        </v-list>
        <v-alert
          v-if="error"

          color="red lighten-2"
          dark
        >
          {{ error }}
        </v-alert>
      </v-card>

      <v-card
        v-if="settings.is_pirate_mode"
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <h2>Local Versions</h2>
        <v-list
          subheader
          two-line
        >
          <version-card
            v-for="image in available_versions['local']"
            :key="image.sha"
            :image="image"
            :current="image.tag === current_version.tag"
            :update-available="updateIsAvailable(image)"
            :deleting="deleting.endsWith(image.tag)"
            @delete="deleteVersion"
            @apply="setVersion"
            @pull-and-apply="pullAndSetVersion"
          />
          <spinning-logo
            v-if="loading_images"
            size="15%"
          />
        </v-list>
      </v-card>
      <v-card
        v-if="settings.is_pirate_mode"
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <h2>Remote Versions</h2>
        <v-form
          @submit.prevent="loadAvailableversions()"
        >
          <v-text-field
            v-model="selected_image"
            label="Remote repository"
          />
        </v-form>
        <v-alert
          v-if="error"

          color="red lighten-2"
          dark
        >
          {{ error }}
        </v-alert>
        <v-list
          subheader
          two-line
        >
          <spinning-logo
            v-if="loading_images"
            size="15%"
          />
          <version-card
            v-for="image in available_versions['remote']"
            :key="image.sha"
            :image="image"
            :remote="true"
            :update-available="updateIsAvailable(image)"
            :show-pull-button="!imageIsAvailableLocally(image.sha)"
            @pull-and-apply="pullAndSetVersion"
          />
        </v-list>
      </v-card>
    </v-col>
    <v-dialog
      v-model="show_pull_output"
      width="auto"
    >
      <v-card>
        <v-card-title class="text-h5 grey lighten-2">
          Pulling new version
        </v-card-title>

        <v-card-text>
          <p
            style="white-space: pre; font-family:monospace;"
          >
            {{ pull_output }}
          </p>
        </v-card-text>

        <v-divider />

        <v-card-actions>
          <v-spacer />
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-card
      v-if="settings.is_pirate_mode"
      max-width="900"
      class="mx-auto pa-4"
    >
      <h2>Manual upload</h2>
      Use this to upload a .tar docker image. These can be download from
      <a href="https://github.com/bluerobotics/BlueOS-docker/actions/workflows/deploy.yml">Github's CI</a>
      or generated locally using "docker save"
      <v-file-input
        id="file"
        show-size
        accept=".tar"
        label="File input"
      />
      <v-progress-linear
        v-if="disable_upload_controls && upload_percentage !== 100"
        class="mb-4"
        :value="upload_percentage"
      />
      <v-btn
        :color="'primary'"
        class="mr-2 mb-4"
        @click="upload()"
        v-text="'Upload'"
      />
    </v-card>
    <v-overlay
      :z-index="10"
      :value="waiting"
    >
      <spinning-logo
        size="100%"
      />
    </v-overlay>
  </div>
</template>

<script lang="ts">
import { gt as sem_ver_greater, SemVer } from 'semver'
import Vue from 'vue'

import settings from '@/libs/settings'
import { Dictionary } from '@/types/common'
import { Version, VersionsQuery } from '@/types/version-chooser'
import back_axios from '@/utils/api'

import SpinningLogo from '../common/SpinningLogo.vue'
import VersionCard from './VersionCard.vue'

export default Vue.extend({
  name: 'VersionChooser',
  components: {
    SpinningLogo,
    VersionCard,
  },
  data() {
    return {
      settings,
      pull_output: '',
      show_pull_output: false,
      available_versions: {
        local: [],
        remote: [],
        error: null,
      } as VersionsQuery,
      latest_stable: undefined as (undefined | string),
      latest_beta: undefined as (undefined | string),
      disable_upload_controls: false,
      upload_percentage: 0,
      current_version: null as (null | Version),
      loading_images: false,
      waiting: false,
      selected_image: 'bluerobotics/blueos-core',
      deleting: '', // image currently being deleted, if any
      error: null as (null | string),
    }
  },
  computed: {
  },
  mounted() {
    this.loadCurrentVersion()
  },
  methods: {
    async checkIfBackendIsOnline() {
      await back_axios({
        method: 'get',
        url: '/version-chooser/v1.0/version/current',
        timeout: 500,
      })
        .then(() => {
          if (this.waiting) {
            // Allow 3 seconds so the user can read the "complete" message
            // reload(true) forces the browser to fetch the page again
            setTimeout(() => { window.location.reload(true) }, 3000)
          }
        })
        .catch((error) => {
          console.log(error)
          this.waiting = true
        })
    },
    fixVersion(version: string) {
      /** It turned out that our semvers are wrong... oopss
      This turns 1.0.0.beta12 into 1.0.0-beta.12
      Additionally filters out tags with no '.' in it, which
      can be improved
      */
      if (version.includes('.beta')) {
        return version.replace('.beta', '-beta.')
      }
      if (!version.includes('.')) {
        return null
      }
      return version
    },
    isSemVer(version: string): boolean {
      // validates a version as SemVer compliant
      try {
        const fixed_version = this.fixVersion(version)
        if (fixed_version == null) {
          return false
        }
        const semver = new SemVer(fixed_version)
        return semver !== null
      } catch (error) {
        return false
      }
    },
    sortVersions(versions: string[]) {
      return versions.sort(
        (a: string, b: string) => {
          const ver_a = this.fixVersion(a)
          const ver_b = this.fixVersion(b)
          if (ver_a === null) {
            return 1
          }
          if (ver_b === null) {
            return -1
          }
          return sem_ver_greater(new SemVer(ver_a), new SemVer(ver_b)) === true ? -1 : 1
        },
      )
    },
    runningBeta() {
      return this.current_version?.tag?.includes('beta') ?? false
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
      if (!this.current_version) {
        return ''
      }
      if (this.latest_stable !== undefined && this.latest_stable !== this.current_version.tag) {
        return this.latest_stable
      }
      return ''
    },
    getLatestBeta() {
      const ordered_list = this.sortVersions(
        this.available_versions.remote.map((image) => image.tag)
          .filter((tag) => this.isSemVer(tag) && tag.includes('beta')),
      )
      return ordered_list ? ordered_list[0] : undefined
    },
    getLatestStable() {
      const ordered_list = this.sortVersions(
        this.available_versions.remote.map((image) => image.tag)
          .filter((tag) => this.isSemVer(tag) && !tag.includes('beta')),
      )
      return ordered_list ? ordered_list[0] : undefined
    },
    sortImages() {
      this.available_versions = {
        local: this.available_versions.local.sort(
          (a: Version, b: Version) => Date.parse(b.last_modified) - Date.parse(a.last_modified),
        ),
        remote: this.available_versions.remote.sort(
          (a: Version, b: Version) => Date.parse(b.last_modified) - Date.parse(a.last_modified),
        ),
        error: this.available_versions.error,
      }
    },
    async loadAvailableversions() {
      this.available_versions = {
        local: [],
        remote: [],
        error: null,
      } as VersionsQuery
      this.loading_images = true
      this.error = null
      await back_axios({
        method: 'get',
        url: `/version-chooser/v1.0/version/available/${this.selected_image}`,
      }).then((response) => {
        this.available_versions = response.data
        this.error = response.data.error
      }).catch(() => {
        this.available_versions = {
          local: [],
          remote: [],
          error: 'Unable to communicate with backend',
        }
      }).finally(() => {
        this.loading_images = false
        this.sortImages()
        this.latest_beta = this.getLatestBeta()
        this.latest_stable = this.getLatestStable()
      })
    },
    async loadCurrentVersion() {
      await back_axios({
        method: 'get',
        url: '/version-chooser/v1.0/version/current/',
      }).then((response) => {
        const image = response.data
        this.current_version = image
        const fullname = `${image.repository}:${image.tag}`
        const [image_first_name] = fullname.split(':')
        this.selected_image = image_first_name
        this.loadAvailableversions()
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
      this.disable_upload_controls = true
      const { files } = document.getElementById('file') as HTMLInputElement
      if (files !== null) {
        await back_axios({
          method: 'POST',
          url: '/version-chooser/v1.0/version/load/',
          timeout: 15 * 60 * 1000, // Wait for 15min
          data: files[0],
          onUploadProgress: (event) => {
            this.upload_percentage = Math.round(100 * (event.loaded / event.total))
          },
        }).finally(() => {
          this.disable_upload_controls = false
          setTimeout(() => { this.loadAvailableversions() }, 3000)
        })
      }
    },
    async pullAndSetVersion(args: string | string[]) {
      const fullname: string = Array.isArray(args) ? args[0] : args
      // This streams the output of docker pull
      this.pull_output = 'Fetching remote image...'
      this.show_pull_output = true
      const [repository, tag] = fullname.split(':')
      const layer_status: Dictionary<string> = {}
      const layers: string[] = []
      const layer_progress: Dictionary<string> = {}
      let overall_status = ''
      let left_over_data = ''

      await back_axios({
        url: '/version-chooser/v1.0/version/pull/',
        method: 'POST',
        data: {
          repository,
          tag,
        },
        onDownloadProgress: (progressEvent) => {
          // dataChunk contains the data that have been obtained so far (the whole data so far)..
          // The received data is descbribed at
          // https://docker-py.readthedocs.io/en/stable/api.html#docker.api.image.ImageApiMixin.pull
          const dataChunk = progressEvent.currentTarget.response
          // As the data consists of multiple jsons, the following like is a hack to split them
          const dataList = (left_over_data + dataChunk.replaceAll('}{', '}\n\n{')).split('\n\n')
          left_over_data = ''

          for (const line of dataList) {
            try {
              const data = JSON.parse(line)
              if ('id' in data) {
                const { id } = data
                if (!layers.includes(id)) {
                  layers.push(id)
                }
                if ('progress' in data) {
                  layer_progress[id] = data.progress
                }
                if ('status' in data) {
                  layer_status[id] = data.status
                }
              } else {
                overall_status = data.status
                // Axios returns the promise too early (before the pull is done)
                // so we check the overall docker status instead
                if (overall_status.includes('Downloaded newer image for')) {
                  setTimeout(() => { this.setVersion(fullname) }, 1000)
                }
                if (overall_status.includes('Image is up to date')) {
                  setTimeout(() => { this.setVersion(fullname) }, 1000)
                }
              }
            } catch (error) {
              left_over_data = line
            }
          }
          this.pull_output = ''
          layers.forEach((image) => {
            this.pull_output = `${this.pull_output}[${image}] ${layer_status[image]}  ${layer_progress[image] || ''}\n`
          })
          this.pull_output = `${this.pull_output}${overall_status}\n`
          // Force it to true again in case the user tried to close the dialog
          this.show_pull_output = true
        },
      }).then(() => setInterval(this.checkIfBackendIsOnline, 1000))
    },
    async setVersion(args: string | string[]) {
      const fullname: string = Array.isArray(args) ? args[0] : args
      const [repository, tag] = fullname.split(':')
      await back_axios({
        method: 'post',
        url: '/version-chooser/v1.0/version/current',
        data: {
          repository,
          tag,
        },
      }).finally(() => setInterval(this.checkIfBackendIsOnline, 1000))
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
        // Remove this image in the frontend, as calling loadAvailableversions()
        // takes a longer time to fetch all images
        this.available_versions.local = this.available_versions.local.filter(
          (element) => element.repository !== repository || element.tag !== tag,
        )
      })
        .catch((error) => { alert(error.response.data) })
        .finally(() => { this.deleting = '' })
    },
    imageIsAvailableLocally(sha: string) : boolean {
      if (!('local' in this.available_versions)) {
        return false
      }
      return this.available_versions.local.some((image) => image.sha === sha)
    },
  },
})
</script>
