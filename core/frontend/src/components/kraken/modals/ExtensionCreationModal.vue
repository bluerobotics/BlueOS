<template>
  <v-dialog
    v-if="extension"
    width="500"
    :value="Boolean(extension)"
    persistent
    @input="showDialog"
    @click:outside="closeDialog"
  >
    <v-card>
      <v-card-title>
        {{ is_editing ? 'Edit' : 'Create' }} Extension
      </v-card-title>

      <v-card-text class="d-flex flex-column">
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
            :rules="[validate_dockerhub]"
          />

          <v-text-field
            v-model="new_extension.tag"
            label="Docker tag"
            :rules="[validate_tag]"
          />

          <v-textarea
            v-if="is_editing"
            v-model="formatted_permissions"
            label="Original Settings"
            :disabled="is_editing"
            :rules="[validate_permissions]"
          />
          <v-textarea
            v-else
            v-model="new_extension.permissions"
            label="Original Settings"
            :disabled="is_editing"
            :rules="[validate_permissions]"
          />

          <v-textarea
            v-if="is_editing"
            v-model="new_extension.user_permissions"
            :label="'Custom settings (these replace regular settings)'"
            :rules="[validate_user_permissions]"
          />

          <v-btn
            color="primary"
            class="mr-4"
            @click="saveExtension"
          >
            {{ is_editing ? 'Save' : 'Create' }}
          </v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { InstalledExtensionData } from '@/types/kraken'
import { VForm } from '@/types/vuetify'

export default Vue.extend({
  name: 'ExtensionCreationModal',
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
      new_extension: this.extension,
    }
  },
  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
    formatted_permissions() {
      return JSON.stringify(JSON.parse(this.new_extension?.permissions ?? '{}'), null, 2)
    },
    is_editing() {
      return this.extension?.editing ?? false
    },
  },
  watch: {
    new_extension() {
      this.$emit('input', this.new_extension)
    },
    extension() {
      this.new_extension = this.extension

      if (this.is_editing && this.new_extension?.permissions) {
        this.new_extension.user_permissions = this.new_extension.permissions
      }
    },
  },
  methods: {
    closeDialog() {
      this.new_extension = null
      this.$emit('closed')
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
    validate_dockerhub(input: string): (true | string) {
      if (input.includes(':')) {
        return 'The name must not contain the docker tag'
      }
      // A tag name must be valid ASCII and may contain lowercase and uppercase letters, digits,
      // underscores, periods and dashes. A tag name may not start with a period or a dash and
      // may contain a maximum of 128 characters.
      // regex based on https://ktomk.github.io/pipelines/doc/DOCKER-NAME-TAG.html#grammar
      const regex = /[a-zA-Z0-9.-]\/[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}/
      if (regex.test(input)) {
        return true
      }
      return 'This field must contain two words separated by a forward slash. '
      + 'Numbers are allowed after the first character. e.g example/docker1'
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
    validate_permissions(input: string): (true | string) {
      try {
        JSON.parse(input)
        return true
      } catch {
        return 'This entry must be in valid JSON format.'
      }
    },
    validate_user_permissions(input: string): (true | string) {
      if (input === '') {
        return true
      }

      try {
        JSON.parse(input)
        return true
      } catch {
        return 'This entry must be in valid JSON format.'
      }
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
      if (this.form.validate() === true) {
        this.$emit('extensionChange', this.new_extension)
      }
    },
    showDialog(state: boolean) {
      if (this.form.validate() === true) {
        this.$emit('change', state)
      }
    },
  },
})
</script>
