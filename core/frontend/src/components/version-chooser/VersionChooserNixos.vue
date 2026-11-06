<template>
  <v-container>
    <v-col
      max-width="1000"
      class="mx-auto"
    >
      <v-card
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <h2>{{ t`Current Version` }}</h2>
        <generation-card
          v-if="status"
          :generation="status.current"
          :latest-stable="latest_stable"
          :activating="activating === status.current.generation"
        />
        <spinning-logo
          v-else
          size="15%"
          :subtitle="t`Loading the running version...`"
        />

        <v-alert
          v-if="status?.installed"
          class="mt-4"
          border="top"
          colored-border
          type="warning"
          elevation="2"
        >
          <div class="d-flex align-center justify-space-between">
            <span>
              <!-- eslint-disable-next-line max-len -->
              {{ t`${status.installed.version} is installed but not running: the machine has to reboot to boot into it.` }}
            </span>
            <v-btn
              color="warning"
              dark
              small
              :disabled="waiting"
              @click="rebootRequired()"
            >
              {{ t`Reboot` }}
            </v-btn>
          </div>
        </v-alert>

        <v-alert
          v-if="status?.pending"
          class="mt-4"
          border="top"
          colored-border
          type="info"
          elevation="2"
        >
          <!-- eslint-disable-next-line max-len -->
          {{ t`Monitoring this version. It is confirmed automatically once its services are up, and the vehicle returns to ${knownGoodLabel} on its own if it does not become healthy.` }}
        </v-alert>

        <v-alert
          v-if="status?.rolled_back_from"
          class="mt-4"
          border="top"
          colored-border
          type="error"
          elevation="2"
          dismissible
        >
          <div class="d-flex align-center justify-space-between">
            <span>
              <!-- eslint-disable-next-line max-len -->
              {{ t`The last update did not pass its health check, so the vehicle rolled back to ${status.current.version}. See` }}
              <a href="#" @click.prevent="showRollbackDetails = !showRollbackDetails">{{ t`details` }}</a>.
            </span>
            <v-btn
              color="warning"
              dark
              small
              :loading="loading"
              :disabled="loading"
              @click="refresh()"
            >
              {{ t`Retry` }}
            </v-btn>
          </div>
          <p
            v-if="showRollbackDetails"
            class="text-caption ma-0 mt-2"
          >
            <!-- eslint-disable-next-line max-len -->
            {{ t`The failed generation was ${status.rolled_back_from}. It is still installed, so it can be inspected or deleted below.` }}
          </p>
        </v-alert>

        <v-alert
          v-if="latest_version"
          class="mt-4"
          border="top"
          colored-border
          type="info"
          elevation="2"
        >
          <div class="d-flex align-center justify-space-between">
            <span>{{ t`BlueOS ${latest_version.version} is available.` }}</span>
            <v-btn
              color="primary"
              :disabled="working"
              :loading="activating === null && upgrading"
              @click="install(latest_version)"
            >
              {{ t`Update to ${latest_version.version}` }}
            </v-btn>
          </div>
        </v-alert>

        <v-alert
          v-if="releases_error"
          class="mt-4"
          color="red lighten-2"
          dark
        >
          <div class="d-flex align-center justify-space-between">
            <span>{{ releases_error }}</span>
            <v-btn
              color="warning"
              dark
              small
              :loading="loading"
              :disabled="loading"
              @click="loadReleases"
            >
              {{ t`Retry` }}
            </v-btn>
          </div>
        </v-alert>
      </v-card>

      <v-card
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <div class="d-flex justify-space-between pb-3">
          <h2>{{ t`Installed Versions` }}</h2>
          <v-btn
            icon
            :loading="loading"
            :disabled="loading"
            @click="refresh()"
          >
            <v-icon>mdi-refresh</v-icon>
          </v-btn>
        </div>
        <p class="text-caption text--secondary">
          <!-- eslint-disable-next-line max-len -->
          {{ t`Every version installed on this card. Switching back to an older one is a rollback you ask for, unlike the automatic one, which only happens when an update fails.` }}
        </p>
        <generation-card
          v-for="generation in generations"
          :key="generation.generation"
          :generation="generation"
          :latest-stable="latest_stable"
          :activating="activating === generation.generation"
          :deleting="deleting === generation.generation"
          :can-delete="canDelete(generation)"
          @activate="activate(generation, $event)"
          @delete="deleteGeneration(generation)"
        />
        <spinning-logo
          v-if="loading && generations.length === 0"
          size="15%"
          :subtitle="t`Loading installed versions...`"
        />
      </v-card>

      <v-card
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <h2>{{ t`Available Versions` }}</h2>
        <p
          v-if="!settings.is_pirate_mode"
          class="text-caption text--secondary"
        >
          {{ t`Turn on Pirate mode to see every published version, including beta and development builds.` }}
        </p>
        <p
          v-else
          class="text-caption text--secondary"
        >
          <!-- eslint-disable-next-line max-len -->
          {{ t`Versions published for this board. Updating downloads the build and installs it for the next boot; if it does not come up healthy, the vehicle returns to the running version.` }}
        </p>
        <release-card
          v-for="release in visible_releases"
          :key="release.toplevel"
          :release="release"
          :latest-stable="latest_stable"
          :installed="isInstalled(release)"
          :upgrade="latest_version?.toplevel === release.toplevel"
          :activating="activating_release === release.version"
          :downloading="downloading_release === release.version"
          @activate="install(release)"
          @download="download(release)"
        />
        <spinning-logo
          v-if="loading && releases.length === 0"
          size="15%"
          :subtitle="t`Loading available versions...`"
        />
        <p
          v-else-if="!loading && releases.length === 0 && !releases_error"
          class="text-caption text--secondary"
        >
          <!-- eslint-disable-next-line max-len -->
          {{ t`This vehicle was built without a release manifest, so there is nothing to download. Versions can still be deployed with nixos-rebuild or deploy-rs, which are protected by the same rollback.` }}
        </p>
      </v-card>

      <v-card
        v-if="settings.is_dev_mode"
        max-width="900"
        class="mx-auto my-12 pa-4"
      >
        <h2>{{ t`Install a store path` }}</h2>
        <p class="text-caption text--secondary">
          <!-- eslint-disable-next-line max-len -->
          {{ t`For a build the manifest does not list, such as one made from a branch. The build has to be in a binary cache already: nothing is compiled here. It becomes a normal version, so it can be rolled back like any other.` }}
        </p>
        <v-form @submit.prevent="installToplevel()">
          <v-text-field
            v-model="toplevel"
            :label="t`System store path`"
            :placeholder="t`/nix/store/...-nixos-system-blueos-...`"
            :error-messages="toplevel_error"
            :disabled="working"
            append-outer-icon="mdi-download"
            clearable
            @click:append-outer="installToplevel()"
          />
        </v-form>
        <v-alert
          v-if="toplevel_log"
          class="mt-4"
          border="top"
          colored-border
          type="error"
          elevation="2"
        >
          <p class="ma-0">
            {{ t`The last attempt did not switch:` }}
          </p>
          <pre class="text-caption mt-2">{{ toplevel_log }}</pre>
        </v-alert>
      </v-card>
    </v-col>
    <v-overlay
      :z-index="10"
      :value="waiting"
    >
      <spinning-logo
        size="100%"
        :subtitle="waiting_text"
      />
    </v-overlay>
  </v-container>
</template>

<script lang="ts">
import { t } from 'ttag'
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import commander from '@/store/commander'
import { ShutdownType } from '@/types/commander'
import { version_chooser_service } from '@/types/frontend_services'
import {
  ActivationMode, ActivationResponse, Generation, Release, Status,
} from '@/types/version-chooser-nixos'
import { isBackendOffline } from '@/utils/api'
import * as VCU from '@/utils/version_chooser_nixos'

import SpinningLogo from '../common/SpinningLogo.vue'
import GenerationCard from './GenerationCard.vue'
import ReleaseCard from './ReleaseCard.vue'

const notifier = new Notifier(version_chooser_service)

/**
 * The daemon activates a generation by restarting the services that changed, so
 * the backend goes away for a moment. Waiting for it to answer again is what
 * tells the user the update actually landed, rather than reloading into a
 * half-restarted system.
 */
const BACKEND_OFFLINE_TIMEOUT_MS = 20000
const BACKEND_ONLINE_TIMEOUT_MS = 120000
/** A switch restarts every service, so it is given the same window the daemon
 * allows it before giving up. */
const ACTIVATION_TIMEOUT_MS = 5 * 60 * 1000
const POLL_INTERVAL_MS = 1000

export default Vue.extend({
  name: 'VersionChooserNixos',
  components: {
    GenerationCard,
    ReleaseCard,
    SpinningLogo,
  },
  data() {
    return {
      settings,
      status: null as (null | Status),
      generations: [] as Generation[],
      releases: [] as Release[],
      releases_error: null as (null | string),
      loading: false,
      waiting: false,
      waiting_text: '',
      activating: null as (null | number),
      activating_release: null as (null | string),
      downloading_release: null as (null | string),
      deleting: null as (null | number),
      upgrading: false,
      showRollbackDetails: false,
      toplevel: '',
      toplevel_error: '',
      toplevel_log: null as (null | string),
    }
  },
  computed: {
    working(): boolean {
      return this.loading || this.waiting
        || this.activating !== null
        || this.activating_release !== null
        || this.downloading_release !== null
    },
    latest_stable(): string {
      return VCU.latestRelease(this.releases, false)?.version ?? ''
    },
    latest_version(): Release | undefined {
      if (!this.status) {
        return undefined
      }
      return VCU.getAvailableUpdate(this.status.current.version, this.releases)
    },
    /** Without pirate mode only the newest stable build is offered. */
    visible_releases(): Release[] {
      const sorted = VCU.sortReleases(this.releases)
      if (this.settings.is_pirate_mode) {
        return sorted.slice(0, 10)
      }
      const stable = sorted.filter((release) => VCU.isSemVer(release.version)
        && !VCU.isPreRelease(release.version))
      return stable.slice(0, 1)
    },
    knownGoodLabel(): string {
      return this.status?.known_good?.generation
        ? t`generation ${this.status.known_good.generation}`
        : t`the last version that worked`
    },
  },
  mounted() {
    this.refresh()
  },
  methods: {
    /**
     * The status endpoint is also how the frontend finds out whether the backend
     * is up at all, so it is polled directly: `back_axios` would treat the
     * restart as an offline backend and reject every call for a while.
     */
    async backendIsOnline(): Promise<boolean> {
      return fetch(`${VCU.UPDATES_API_URL}/status`, { method: 'GET' })
        .then((response) => response.ok)
        .catch(() => false)
    },

    async waitForBackend(offline_first: boolean): Promise<void> {
      const deadline = Date.now() + (offline_first ? BACKEND_OFFLINE_TIMEOUT_MS : BACKEND_ONLINE_TIMEOUT_MS)
      const want_online = !offline_first

      while (Date.now() < deadline) {
        // eslint-disable-next-line no-await-in-loop
        const online = await this.backendIsOnline()
        if (online === want_online) {
          return
        }
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => { setTimeout(resolve, POLL_INTERVAL_MS) })
      }
      throw new Error('the update daemon did not come back in time')
    },

    async refresh(): Promise<void> {
      this.loading = true
      await Promise.all([this.loadStatus(), this.loadGenerations(), this.loadReleases()])
      this.loading = false
    },

    async loadStatus(): Promise<void> {
      await VCU.loadStatus()
        .then((status) => { this.status = status })
        .catch((error) => {
          if (isBackendOffline(error)) {
            return
          }
          const message = t`Could not read the update status: ${VCU.describeError(error)}`
          notifier.pushError('VERSION_CHOOSER_STATUS_FAIL', message)
        })
    },

    async loadGenerations(): Promise<void> {
      await VCU.loadGenerations()
        .then((generations) => { this.generations = generations })
        .catch((error) => {
          if (isBackendOffline(error)) {
            return
          }
          const message = t`Could not list the installed versions: ${VCU.describeError(error)}`
          notifier.pushError('VERSION_CHOOSER_GENERATIONS_FAIL', message)
        })
    },

    async loadReleases(): Promise<void> {
      await VCU.loadReleases()
        .then((response) => {
          this.releases = response.releases
          this.releases_error = response.error
        })
        .catch((error) => {
          if (isBackendOffline(error)) {
            return
          }
          this.releases_error = VCU.describeError(error)
        })
    },

    async activate(generation: Generation, mode: ActivationMode): Promise<void> {
      this.activating = generation.generation
      this.waiting = true
      this.waiting_text = mode === 'boot'
        ? t`Installing ${generation.version}...`
        : t`Switching to ${generation.version}...`
      try {
        const outcome = await VCU.activateGeneration(generation.generation, mode)
        // `boot` leaves the running system alone, so there is nothing to wait
        // for: the generation only takes over at the next reboot.
        if (!outcome.reboot_required) {
          this.waiting_text = t`Waiting for the switch to finish...`
          await this.waitForActivation(outcome, generation.version)
          window.location.reload()
          return
        }
        notifier.pushSuccess(
          'VERSION_CHOOSER_ACTIVATE_SUCCESS',
          t`${generation.version} is installed. Reboot to boot into it.`,
          true,
        )
      } catch (error) {
        notifier.pushError(
          'VERSION_CHOOSER_ACTIVATE_FAIL',
          t`Could not switch to ${generation.version}: ${VCU.describeError(error)}`,
          true,
        )
      } finally {
        this.activating = null
        this.waiting = false
        await this.refresh()
      }
    },

    /**
     * The daemon answers an activation with 202 and then gets restarted by the
     * switch it started, so there is no response left to read the outcome from.
     * Polling `/status` is, and it ends when the generation we asked for is what
     * is running. Waiting for the daemon to go away first would race: a fast
     * switch can finish before a poll ever observes it offline.
     */
    async waitForActivation(outcome: ActivationResponse, label: string): Promise<void> {
      const deadline = Date.now() + ACTIVATION_TIMEOUT_MS

      while (Date.now() < deadline) {
        // eslint-disable-next-line no-await-in-loop
        const status = await VCU.loadStatus().catch(() => undefined)
        if (status?.current.toplevel === outcome.toplevel) {
          return
        }
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => { setTimeout(resolve, POLL_INTERVAL_MS) })
      }

      // The daemon is back but still reports the old generation, so the switch
      // failed after it started. Its output is the only account of why.
      const status = await VCU.loadStatus().catch(() => undefined)
      const detail = status?.last_switch_log ?? t`no output was recorded`
      throw new Error(t`${label} did not start within the deadline: ${detail}`)
    },

    async install(release: Release): Promise<void> {
      this.activating_release = release.version
      this.waiting = true
      this.waiting_text = t`Downloading ${release.version}...`
      try {
        await VCU.activateRelease(release.version, 'boot')
        notifier.pushSuccess(
          'VERSION_CHOOSER_INSTALL_SUCCESS',
          t`${release.version} is installed. Reboot to boot into it.`,
          true,
        )
        await this.refresh()
      } catch (error) {
        notifier.pushError(
          'VERSION_CHOOSER_INSTALL_FAIL',
          t`Could not install ${release.version}: ${VCU.describeError(error)}`,
          true,
        )
      } finally {
        this.activating_release = null
        this.waiting = false
      }
    },

    /**
     * Installing by store path is for builds the manifest does not list, so the
     * chooser has no published metadata to show for the result; the daemon's
     * message is what names the build on failure.
     */
    async installToplevel(): Promise<void> {
      const toplevel = this.toplevel.trim()
      this.toplevel_error = ''
      this.toplevel_log = null

      if (!VCU.isStorePath(toplevel)) {
        this.toplevel_error = t`That is not a /nix/store path to a system build.`
        return
      }

      this.waiting = true
      this.waiting_text = t`Downloading the build...`
      try {
        await VCU.activateToplevel(toplevel, 'boot')
        this.toplevel = ''
        notifier.pushSuccess(
          'VERSION_CHOOSER_TOPLEVEL_SUCCESS',
          t`The build is installed. Reboot to boot into it.`,
          true,
        )
        await this.refresh()
      } catch (error) {
        this.toplevel_log = VCU.describeError(error)
        notifier.pushError(
          'VERSION_CHOOSER_TOPLEVEL_FAIL',
          t`Could not install that build: ${VCU.describeError(error)}`,
          true,
        )
      } finally {
        this.waiting = false
      }
    },

    async download(release: Release): Promise<void> {
      this.downloading_release = release.version
      try {
        await VCU.downloadRelease(release.version)
        notifier.pushSuccess(
          'VERSION_CHOOSER_DOWNLOAD_SUCCESS',
          t`${release.version} is downloaded and can be installed without internet.`,
        )
        await this.refresh()
      } catch (error) {
        notifier.pushError(
          'VERSION_CHOOSER_DOWNLOAD_FAIL',
          t`Could not download ${release.version}: ${VCU.describeError(error)}`,
          true,
        )
      } finally {
        this.downloading_release = null
      }
    },

    async deleteGeneration(generation: Generation): Promise<void> {
      const label = t`${generation.version} (generation ${generation.generation})`
      if (!window.confirm(t`Delete ${label}? The build can be downloaded again if it is published.`)) {
        return
      }
      this.deleting = generation.generation
      try {
        await VCU.deleteGeneration(generation.generation)
        notifier.pushSuccess('VERSION_CHOOSER_DELETE_SUCCESS', t`Deleted ${label}.`)
        await this.refresh()
      } catch (error) {
        notifier.pushError(
          'VERSION_CHOOSER_DELETE_FAIL',
          t`Could not delete ${label}: ${VCU.describeError(error)}`,
          true,
        )
      } finally {
        this.deleting = null
      }
    },

    /**
     * The daemon refuses to delete the running generation and the rollback
     * target, so the button is only offered where it can succeed.
     */
    canDelete(generation: Generation): boolean {
      return !generation.current && !generation.known_good
    },

    isInstalled(release: Release): boolean {
      return this.generations.some((generation) => generation.toplevel === release.toplevel)
    },

    async rebootRequired(): Promise<void> {
      this.waiting = true
      this.waiting_text = t`Waiting for the vehicle to reboot...`
      await commander.shutdown(ShutdownType.Reboot)
      try {
        await this.waitForBackend(true)
        await this.waitForBackend(false)
        window.location.reload()
      } catch (error) {
        notifier.pushError(
          'VERSION_CHOOSER_REBOOT_FAIL',
          t`The vehicle did not come back in time: ${VCU.describeError(error)}`,
          true,
        )
        this.waiting = false
      }
    },
  },
})
</script>
