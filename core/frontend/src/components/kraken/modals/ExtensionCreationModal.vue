<template>
  <v-dialog
    v-if="extension"
    width="700"
    :value="Boolean(extension)"
    persistent
    @input="showDialog"
    @click:outside="closeDialog"
    @keydown.ctrl.enter.prevent="saveExtension"
  >
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>{{ is_editing ? 'Edit' : (is_from_upload ? 'Configure Uploaded' : 'Create') }} Extension</span>
        <v-btn
          icon
          x-small
          class="ml-2"
          :color="copySuccess ? 'success' : undefined"
          title="Copy configuration"
          @click="copyConfig"
        >
          <v-icon small>
            {{ copySuccess ? 'mdi-check' : 'mdi-content-copy' }}
          </v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text
        class="d-flex flex-column"
        @paste="handlePaste"
      >
        <v-form
          ref="form"
          lazy-validation
        >
          <v-text-field
            v-model="new_extension.identifier"
            label="Extension Identifier"
            placeholder="yourorganization.yourextension"
            :disabled="is_editing"
            :rules="[validate_identifier]"
          />

          <v-text-field
            v-model="new_extension.name"
            label="Extension Name"
            :rules="[validate_name]"
          />

          <v-text-field
            v-model="new_extension.docker"
            label="Docker image"
            :disabled="is_editing"
            :rules="[validate_imagename]"
          />

          <v-text-field
            v-model="new_extension.tag"
            label="Docker tag"
            :rules="[validate_tag]"
            @paste="handleTagPaste"
          />

          <div class="permissions-editor">
            <json-editor
              v-model="new_permissions"
              class="permissions-editor-surface"
              style="width:100%; min-height:400px"
            >
              <template #controls>
                <v-btn
                  v-if="manifestMissing"
                  v-tooltip="'Manifest not found for this image and tag'"
                  class="editor-control"
                  icon
                  color="warning"
                >
                  <v-icon>mdi-alert</v-icon>
                </v-btn>
                <v-btn
                  v-if="is_reset_editing_permissions_visible"
                  v-tooltip="'Reset to default permissions'"
                  class="editor-control"
                  icon
                  color="white"
                  @click="resetToDefaultPermissions"
                >
                  <v-icon>mdi-restore</v-icon>
                </v-btn>
              </template>
            </json-editor>
            <v-overlay
              :value="permissionsLoading"
              absolute
            >
              <spinning-logo
                size="100"
                subtitle="Loading permissions"
              />
            </v-overlay>
          </div>
        </v-form>
      </v-card-text>
      <v-card-actions
        class="pt-1"
      >
        <v-spacer />
        <v-btn
          color="primary"
          class="mr-4"
          :disabled="!valid_permissions || permissionsLoading || permissionsFetchPending"
          @click="saveExtension"
        >
          {{ is_editing ? 'Save' : (is_from_upload ? 'Install' : 'Create') }}
        </v-btn>
      </v-card-actions>
    </v-card>
    <warning-dialog
      v-model="showManifestWarning"
      title="Manifest not found"
      :message="noManifestWarningMessage"
      confirm-label="Continue anyway"
      @confirm="commitExtension"
    />
  </v-dialog>
</template>

<script lang="ts">
import { isEqual } from 'lodash'
import Vue, { PropType } from 'vue'

import JsonEditor from '@/components/common/JsonEditor.vue'
import SpinningLogo from '@/components/common/SpinningLogo.vue'
import WarningDialog from '@/components/common/WarningDialog.vue'
import { fetchExtensionPermissions } from '@/components/kraken/KrakenManager'
import { copyToClipboard } from '@/cosmos'
import Notifier from '@/libs/notifier'
import { kraken_service } from '@/types/frontend_services'
import { InstalledExtensionData } from '@/types/kraken'
import { VForm } from '@/types/vuetify'

// The image and tag are still being typed. A shorter wait starts a lookup on every pause.
const PERMISSION_FETCH_DEBOUNCE_MS = 1000
const notifier = new Notifier(kraken_service)

export default Vue.extend({
  name: 'ExtensionCreationModal',
  components: {
    JsonEditor,
    SpinningLogo,
    WarningDialog,
  },
  model: {
    prop: 'extension',
    event: 'change',
  },
  props: {
    extension: {
      type: Object as PropType<InstalledExtensionData & { editing: boolean } | null>,
      default: null,
    },
    tempTag: {
      type: String,
      default: null,
    },
  },

  data() {
    return {
      new_extension: this.extension ?? {
        identifier: '',
        name: '',
        docker: '',
        tag: '',
        permissions: '{}',
        editing: false,
      } as InstalledExtensionData & { editing: boolean },
      new_permissions: JSON.parse(this.extension?.permissions ?? '{}'),
      copySuccess: false,
      permissionsRequestId: 0,
      permissionsLoading: false,
      permissionsFetchPending: false,
      manifestMissing: false,
      showManifestWarning: false,
      permissionsFetchSuppressedFor: null as string | null,
      permissionsFetchTimeout: undefined as ReturnType<typeof setTimeout> | undefined,
    }
  },
  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
    is_editing() {
      return this.extension?.editing ?? false
    },
    is_from_upload() {
      return Boolean(this.tempTag)
    },
    is_reset_editing_permissions_visible() {
      return !this.samePermissions(this.new_permissions, this.new_extension?.permissions)
    },
    valid_permissions() {
      return this.new_permissions
    },
    noManifestWarningMessage(): string {
      return (
        'No manifest was found for this image and tag, so the image might be missing. '
          + 'Double-check the name and tag before continuing.'
      )
    },
  },
  watch: {
    new_extension() {
      this.$emit('input', this.new_extension)
    },
    newPermissions(new_permissions: unknown) {
      this.new_extension.user_permissions = this.samePermissions(new_permissions, this.new_extension.permissions)
        ? ''
        : JSON.stringify(new_permissions)
    },
    extension() {
      if (this.extension) {
        this.new_extension = { ...this.extension }
      } else {
        this.new_extension = {
          identifier: '',
          name: '',
          docker: '',
          tag: '',
          permissions: '{}',
          editing: false,
        } as InstalledExtensionData & { editing: boolean }
      }
      this.populatePermissions()
    },
  },
  created() {
    // Paste sets the image and then the tag. One watcher sees both before scheduling a lookup.
    this.$watch(
      () => [this.new_extension.docker, this.new_extension.tag],
      this.schedulePermissionsFetch,
      { deep: false },
    )
  },
  mounted() {
    this.populatePermissions()
  },
  beforeDestroy() {
    clearTimeout(this.permissionsFetchTimeout)
    this.permissionsRequestId += 1
  },
  methods: {
    schedulePermissionsFetch(): void {
      clearTimeout(this.permissionsFetchTimeout)
      const requestId = this.permissionsRequestId + 1
      this.permissionsRequestId = requestId
      this.permissionsFetchPending = false

      if (this.is_editing || this.is_from_upload) {
        this.permissionsLoading = false
        return
      }

      const docker = this.new_extension.docker?.trim()
      const tag = this.new_extension.tag?.trim()
      if (!docker || !tag || this.validate_imagename(docker) !== true || this.validate_tag(tag) !== true) {
        this.permissionsLoading = false
        return
      }
      if (this.permissionsFetchSuppressedFor === `${docker}:${tag}`) {
        this.permissionsFetchSuppressedFor = null
        this.permissionsLoading = false
        return
      }

      this.permissionsLoading = false
      this.permissionsFetchPending = true
      this.permissionsFetchTimeout = setTimeout(() => {
        this.permissionsFetchPending = false
        this.manifestMissing = false
        this.permissionsLoading = true
        this.fetchRemotePermissions(requestId, docker, tag)
      }, PERMISSION_FETCH_DEBOUNCE_MS)
    },
    async fetchRemotePermissions(requestId: number, docker: string, tag: string): Promise<void> {
      try {
        const permissions = await fetchExtensionPermissions(docker, tag)
        if (requestId !== this.permissionsRequestId) {
          return
        }
        this.new_extension.permissions = JSON.stringify(permissions)
        this.new_permissions = permissions
      } catch (error) {
        if (requestId !== this.permissionsRequestId) {
          return
        }
        this.manifestMissing = this.isManifestMissing(error)
        if (this.manifestMissing) {
          this.new_extension.permissions = '{}'
          this.new_permissions = {}
        } else {
          notifier.pushWarning(
            'EXTENSION_PERMISSIONS_FETCH_FAIL',
            this.permissionsFailureMessage(docker, tag, error),
            true,
          )
        }
      } finally {
        if (requestId === this.permissionsRequestId) {
          this.permissionsLoading = false
        }
      }
    },
    isManifestMissing(error: unknown): boolean {
      const { response } = error as { response?: { status?: number } }
      return response?.status === 404
    },
    permissionsFailureMessage(docker: string, tag: string, error: unknown): string {
      const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
      let reason = 'The registry lookup failed.'
      if (typeof detail === 'string' && detail) {
        reason = detail
      } else if (error instanceof Error && error.message) {
        reason = error.message
      }
      return `Could not read permissions for ${docker}:${tag}: ${reason}`
    },
    populatePermissions() {
      const user_permissions = JSON.parse(this.extension?.user_permissions || '{}')
      if (Object.keys(user_permissions).length > 0) {
        this.new_permissions = user_permissions
        return
      }
      this.new_permissions = JSON.parse(this.extension?.permissions || '{}')
    },
    closeDialog() {
      this.new_extension = {
        identifier: '',
        name: '',
        docker: '',
        tag: '',
        permissions: '{}',
        editing: false,
      } as InstalledExtensionData & { editing: boolean }
      this.$emit('closed')
    },
    samePermissions(value: unknown, defaults: string | undefined): boolean {
      try {
        return isEqual(value, JSON.parse(defaults || '{}'))
      } catch {
        return false
      }
    },
    resetToDefaultPermissions() {
      this.new_permissions = JSON.parse(this.new_extension?.permissions || '{}')
    },
    validate_identifier(input: string): (true | string) {
      // Identifiers should be two words separated by a period
      // They can contain lower and uppercase characters, but cannot begin with a number
      if (/\s/.test(input)) {
        return 'This field must not contain whitespace.'
      }
      const name_validator = '[A-Za-z][A-Za-z0-9]+'
      const regex = RegExp(`^${name_validator}\\.${name_validator}`)
      if (regex.test(input)) {
        return true
      }
      return 'This field must contain two words separated by a period. Numbers are allowed after the first character.'
    },
    validate_imagename(input: string): (true | string) {
      // See https://github.com/distribution/reference/blob/main/reference.go
      const path_part_regex = /^[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*$/

      if (!input) return 'Name must not be empty'
      if (/\s/.test(input)) return 'Name must not contain whitespace'

      const parts = input.split('/')

      for (const [i, part] of parts.entries()) {
        if (i === 0 && parts.length >= 2) {
          // note the domain is optional; we could just have a path.
          // But if a domain is present, it has looser parsing rules.
          if (!URL.canParse(`http://${part}`)) {
            return 'Name has an invalid domain'
          }
        } else if (i === parts.length - 1 && part.includes(':')) {
          return 'Name must not contain a tag'
        } else if (!path_part_regex.test(part)) {
          return 'Name is invalid'
        }
      }

      return true
    },
    validate_name(input: string): (true | string) {
      // Trim only for checks so a space while typing the next word is not an error.
      const name = input.trim()
      if (name.length === 0) {
        return 'This field must not be empty.'
      }
      if (name.length > 128) {
        return 'This entry must fit within 128 characters.'
      }
      return true
    },
    validate_tag(input: string) {
      if (!input) {
        return 'Tag name must not be empty.'
      }
      if (/\s/.test(input)) {
        return 'Tag name must not include spaces.'
      }
      if (input.startsWith('-') || input.startsWith('.')) {
        return 'Tag name must not start with a period or a dash.'
      }
      if (input.length > 127) {
        return 'Tag name must be shorter than 128 characters.'
      }
      const re = /[^A-Za-z0-9\-_.]/
      if (re.test(input)) {
        return 'Only letters, numbers, dashes, periods, and underscores are allowed.'
      }
      return true
    },
    async saveExtension(): Promise<void> {
      if (!this.prepareExtension()) {
        return
      }
      if (this.manifestMissing) {
        this.showManifestWarning = true
        return
      }
      this.commitExtension()
    },
    prepareExtension(): boolean {
      if (this.new_permissions) {
        this.new_extension.user_permissions = this.samePermissions(
          this.new_permissions,
          this.new_extension.permissions,
        )
          ? ''
          : JSON.stringify(this.new_permissions)
      }
      this.new_extension.name = this.new_extension.name.trim()
      return this.form.validate() === true
    },
    commitExtension(): void {
      this.$emit('extensionChange', this.new_extension)
    },
    showDialog(state: boolean) {
      if (this.form.validate() === true) {
        this.$emit('change', state)
      }
    },
    async copyConfig() {
      if (!this.new_extension) {
        return
      }

      const config = {
        identifier: this.new_extension.identifier,
        name: this.new_extension.name,
        docker: this.new_extension.docker,
        tag: this.new_extension.tag,
        permissions: this.new_extension.permissions !== '{}'
          ? this.new_extension.permissions : this.new_extension.user_permissions,
      }

      const jsonString = JSON.stringify(config, null, 2)
      const success = await copyToClipboard(jsonString)

      if (success) {
        this.copySuccess = true
        setTimeout(() => {
          this.copySuccess = false
        }, 2000) // Reset after 2 seconds
      }
    },
    handleTagPaste(event: ClipboardEvent) {
      const pastedText = event.clipboardData?.getData('text')?.trim()
      if (!pastedText) return

      const colonIdx = pastedText.lastIndexOf(':')
      if (colonIdx >= 0 && colonIdx < pastedText.length - 1) {
        event.preventDefault()
        this.new_extension.tag = pastedText.slice(colonIdx + 1)
      }
    },
    handlePaste(event: ClipboardEvent) {
      try {
        // Get the pasted text
        const pastedText = event.clipboardData?.getData('text')
        if (!pastedText) return

        // Try to parse it as JSON
        const config = JSON.parse(pastedText)

        // Validate that it has the expected structure
        if (config.identifier && config.name && config.docker && config.tag) {
          // Prevent the default paste
          event.preventDefault()

          // Update the form data
          if (!this.new_extension) {
            this.new_extension = {} as InstalledExtensionData & { editing: boolean }
          }

          // The image watcher fetches permissions, while a pasted config already has them
          this.permissionsFetchSuppressedFor = config.permissions
            ? `${config.docker.trim()}:${config.tag.trim()}`
            : null
          this.new_extension.identifier = config.identifier
          this.new_extension.name = config.name
          this.new_extension.docker = config.docker
          this.new_extension.tag = config.tag
          if (config.permissions) {
            this.new_extension.permissions = typeof config.permissions === 'string'
              ? config.permissions
              : JSON.stringify(config.permissions)
            this.new_permissions = JSON.parse(this.new_extension.permissions)
          }
        }
      } catch (error) {
        // Not valid JSON or doesn't match our format - ignore
        console.debug('Pasted content was not valid extension configuration')
      }
    },
  },
})
</script>

<style scoped>
.permissions-editor {
  position: relative;
}

.permissions-editor-surface {
  position: relative;
  z-index: 0;
}
</style>
