<template>
  <v-card>
    <v-card-subtitle class="text-center pt-6">
      Log in using your Docker Hub credentials to access private repositories
      and benefit from an increased rate limit.
    </v-card-subtitle>

    <SpinningLogo
      v-if="op_loading"
      size="100px"
      :subtitle="op_description"
    />
    <div v-else>
      <v-tabs
        v-model="tab"
        fixed-tabs
        @change="onTabChange"
      >
        <v-tab key="0" href="#0" class="tab-text">
          <v-icon class="mr-3">
            mdi-login
          </v-icon>
          Login
        </v-tab>
        <v-tab key="1" href="#1" class="tab-text">
          <v-icon class="mr-3">
            mdi-account
          </v-icon>
          Accounts
        </v-tab>
      </v-tabs>
      <v-card-text v-if="is_login_tab">
        <div class="d-flex justify-space-around">
          <v-switch
            v-model="log_in_info.root"
            label="Login root user"
            class="pb-3"
          />
          <v-switch
            v-model="use_custom_registry"
            label="Custom registry"
            class="pb-3"
          />
        </div>

        <v-text-field
          v-if="use_custom_registry"
          v-model="log_in_info.registry"
          class="pb-3"
          label="Custom Registry"
          outlined
          hide-details
        />

        <v-text-field
          v-model="log_in_info.username"
          class="pb-3"
          label="Docker Username"
          outlined
          hide-details
        />

        <v-text-field
          v-model="log_in_info.password"
          label="Docker Password or PAT"
          type="password"
          outlined
          hide-details
        />
      </v-card-text>
      <v-card-text v-if="is_accounts_tab">
        <v-list
          v-if="has_some_account"
        >
          <v-list-item
            v-for="account in accounts"
            :key="account.username"
          >
            <v-list-item-content>
              <v-list-item-title>
                {{ account.username }}
              </v-list-item-title>
              <v-list-item-subtitle>
                {{ account.registry }}
              </v-list-item-subtitle>
            </v-list-item-content>
            <div v-if="account.root">
              <v-tooltip bottom>
                <template #activator="{ on }">
                  <v-icon v-on="on">
                    mdi-shield-account
                  </v-icon>
                </template>
                <span>Used by root user</span>
              </v-tooltip>
            </div>
            <v-list-item-action>
              <v-btn
                icon
                @click="logout(account.username, account.registry)"
              >
                <v-icon>mdi-logout</v-icon>
              </v-btn>
            </v-list-item-action>
          </v-list-item>
        </v-list>
        <v-card-subtitle
          v-else
          class="text-center pt-6"
        >
          No connected accounts
        </v-card-subtitle>
      </v-card-text>
    </div>
    <v-alert
      v-if="has_error"
      class="mx-4"
      type="error"
    >
      {{ op_error }}
    </v-alert>
    <v-alert
      v-if="has_success"
      class="mx-4"
      type="success"
    >
      {{ op_success }}
    </v-alert>
    <v-card-actions class="justify-center pb-4">
      <v-btn
        color="primary"
        @click="$emit('cancel')"
      >
        Cancel
      </v-btn>
      <v-spacer />
      <v-btn
        color="success"
        @click="login"
      >
        Login
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import { DockerLoginInfo } from '@/types/version-chooser'
import { dockerAccounts, dockerLogin, dockerLogout } from '@/utils/version_chooser'

const DEFAULT_DOCKER_REGISTRY = 'https://index.docker.io/v1/'

const DEFAULT_LOG_IN_INFO = {
  root: false,
  registry: DEFAULT_DOCKER_REGISTRY,
  username: '',
  password: '',
} as DockerLoginInfo

export default Vue.extend({
  name: 'VersionCard',
  components: {
    SpinningLogo,
  },
  data() {
    return {
      tab: '0',

      log_in_info: { ...DEFAULT_LOG_IN_INFO },
      use_custom_registry: false,

      accounts: [] as DockerLoginInfo[],

      op_loading: false,
      op_description: '',
      op_error: undefined as string | undefined,
      op_success: undefined as string | undefined,
    }
  },
  computed: {
    has_error(): boolean {
      return this.op_error !== undefined
    },
    has_success(): boolean {
      return this.op_success !== undefined
    },
    has_some_account(): boolean {
      return this.accounts.length > 0
    },
    is_login_tab(): boolean {
      return this.tab === '0'
    },
    is_accounts_tab(): boolean {
      return this.tab === '1'
    },
  },
  async mounted() {
    await this.fetchAccounts()
  },
  methods: {
    cleanAlerts() {
      this.op_error = undefined
      this.op_success = undefined
    },
    prepareOperation(description: string) {
      this.op_error = undefined
      this.op_success = undefined
      this.op_loading = true
      this.op_description = description
    },
    resetInput() {
      this.log_in_info = { ...DEFAULT_LOG_IN_INFO }
      this.use_custom_registry = false
    },
    async onTabChange() {
      this.cleanAlerts()
      await this.fetchAccounts()
    },
    async login() {
      this.prepareOperation('Logging in to Docker Hub...')

      try {
        await dockerLogin(this.log_in_info)

        this.resetInput()
        this.op_success = 'Successfully added account in Docker Daemon.'
      } catch (op_error) {
        this.op_error = String(op_error ?? 'Failed to login to Docker Hub.')
      } finally {
        this.op_loading = false
      }
    },
    async logout(username: string, registry?: string) {
      this.prepareOperation('Logging out from Docker Hub...')

      try {
        const data = {
          username,
          registry,
        } as DockerLoginInfo

        await dockerLogout(data)
        await this.fetchAccounts()
      } catch (op_error) {
        this.op_error = String(op_error ?? 'Failed to logout to Docker Hub.')
      } finally {
        this.op_loading = false
      }
    },
    async fetchAccounts() {
      this.prepareOperation('Fetching connected accounts...')

      try {
        this.accounts = await dockerAccounts()
      } catch (op_error) {
        this.op_error = String(op_error ?? 'Failed to list connected accounts.')
      } finally {
        this.op_loading = false
      }
    },
  },
})
</script>
