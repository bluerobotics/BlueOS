<template>
  <v-dialog
    v-if="extension"
    width="700"
    :value="Boolean(extension)"
    persistent
    @input="showDialog"
    @click:outside="closeDialog"
  >
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>{{ is_editing ? 'Edit' : 'Create' }} Extension</span>
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
          />

          <json-editor
            v-model="new_permissions"
            style="width:100%; min-height:400px"
          >
            <template
              v-if="is_reset_editing_permissions_visible"
              #controls
            >
              <v-btn
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
        </v-form>
      </v-card-text>
      <v-card-actions
        class="pt-1"
      >
        <v-spacer />
        <v-btn
          color="primary"
          class="mr-4"
          :disabled="!valid_permissions"
          @click="saveExtension"
        >
          {{ is_editing ? 'Save' : 'Create' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import JsonEditor from '@/components/common/JsonEditor.vue'
import { copyToClipboard } from '@/cosmos'
import { InstalledExtensionData } from '@/types/kraken'
import { VForm } from '@/types/vuetify'

export default Vue.extend({
  name: 'ExtensionCreationModal',
  components: {
    JsonEditor,
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
    }
  },
  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
    is_editing() {
      return this.extension?.editing ?? false
    },
    is_reset_editing_permissions_visible() {
      return this.new_permissions !== this.extension?.permissions
    },
    valid_permissions() {
      return this.new_permissions
    },
  },
  watch: {
    new_extension() {
      this.$emit('input', this.new_extension)
    },
    new_permissions(new_permissions: string) {
      this.new_extension.user_permissions = JSON.stringify(new_permissions)
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
  mounted() {
    this.populatePermissions()
  },
  methods: {
    populatePermissions() {
      const user_permissions = JSON.parse(this.extension?.user_permissions ?? '{}')
      const original_permissions = JSON.parse(this.extension?.permissions ?? '{}')
      if (user_permissions) {
        this.new_permissions = user_permissions
      } else {
        this.new_permissions = original_permissions
      }
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
    resetToDefaultPermissions() {
      if (this.new_extension) {
        this.new_permissions = JSON.parse(this.extension?.permissions ?? '{}')
      }
    },
    validate_identifier(input: string): (true | string) {
      // Identifiers should be two words separated by a period
      // They can contain lower and uppercase characters, but cannot begin with a number
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
      if (input.trim().length === 0) {
        return 'This field must not be empty.'
      }
      if (input.length > 128) {
        return 'This entry must fit within 128 characters.'
      }
      return true
    },
    validate_tag(input: string) {
      if (input.includes(' ')) {
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
      if (this.new_permissions) {
        this.new_extension.user_permissions = JSON.stringify(this.new_permissions)
      }
      if (this.form.validate() === true) {
        this.$emit('extensionChange', this.new_extension)
      }
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
        permissions: this.new_extension.permissions,
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

          this.new_extension.identifier = config.identifier
          this.new_extension.name = config.name
          this.new_extension.docker = config.docker
          this.new_extension.tag = config.tag

          // Handle permissions if present
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
