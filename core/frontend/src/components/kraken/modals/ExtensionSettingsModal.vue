<template>
  <v-dialog v-model="settings_open" width="500px">
    <v-card min-width="100%">
      <v-app-bar>
        <v-toolbar-title>Extensions Manifest</v-toolbar-title>
        <v-spacer />
      </v-app-bar>
      <v-card class="px-3 pb-3 mx-2" elevation="0">
        <v-list>
          <v-card-subtitle class="text-md-center" max-width="30">
            Drag manifest sources to set priority. <br /><b>Top ones have higher priority.</b>
          </v-card-subtitle>
          <draggable v-model="manifests">
            <v-card
              v-for="(element, index) in manifests"
              :key="index"
              class="pl-3 ma-2 pa-1 d-flex align-center justify-center"
              style="cursor: pointer;"
            >
              {{ order(index + 1) }}
              <v-spacer />
              <p
                class="ma-0 pa-0"
                :class="element.enabled ? '' : 'disabled-source-name'"
              >
                <span
                  class="ma-0 pa-0"
                  :class="element.enabled ? '' : 'disabled-source-name-text'"
                >
                  {{ element.name }}
                </span>
              </p>
              <v-spacer />
              <v-btn
                icon
                :disabled="element.factory"
                tooltip="Delete Source"
                @click="removeSource(element.identifier)"
              >
                <v-icon>mdi-delete</v-icon>
              </v-btn>
              <v-btn
                icon
                @click="setEditingModal(element)"
              >
                <v-icon>{{ element.factory ? 'mdi-pencil-lock' : 'mdi-pencil' }}</v-icon>
              </v-btn>
              <v-icon v-text="'mdi-drag'" />
            </v-card>
          </draggable>
          <v-card
            class="ma-2 py-1 mt-4 d-flex align-center justify-center"
            @click.prevent="setCreateModal"
          >
            <v-spacer />
            <v-icon>mdi-plus</v-icon>
            <v-spacer />
          </v-card>
        </v-list>
        <v-alert
          v-if="has_operation_error"
          class="mx-2"
          type="error"
        >
          {{ operation_error }}
        </v-alert>
        <v-progress-linear
          v-if="operation_loading"
          indeterminate
          min-width="300"
        />
        <v-divider />
        <v-card-actions class="justify-center mt-1">
          <v-btn
            color="primary"
            @click="settings_open = false"
          >
            Cancel
          </v-btn>
          <v-spacer />
          <v-btn
            color="success"
            @click="reorderSources"
          >
            Apply
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-card>
    <v-dialog v-model="operation_open" width="600px">
      <v-card elevation="0">
        <v-card-title class="mb-7">
          {{ is_editing ? 'Update Source' : 'Add a new source' }}
        </v-card-title>
        <v-card-subtitle class="text-md-center" max-width="30">
          <b>Factory sources can only be enabled/disabled.</b>
        </v-card-subtitle>
        <v-text-field
          v-model="source_url"
          :disabled="is_factory"
          class="mx-6"
          label="URL"
          :error="is_operation_url_invalid"
          outlined
          dense
          @input="deductNameFromURL"
        />
        <v-text-field
          v-model="source_name"
          :disabled="is_factory"
          class="mx-6"
          label="Name"
          outlined
          dense
          @input="blockNameAutoComplete"
        />
        <v-checkbox
          v-model="source_enabled"
          class="mx-6 mt-0"
          label="Source Enabled"
        />
        <v-alert
          v-if="is_operation_url_invalid"
          class="mx-9"
          type="error"
        >
          This source contains an invalid manifest URL.
          <v-checkbox
            v-model="should_bypass_validate"
            class="my-0 pt-4"
            label="Continue anyway"
          />
        </v-alert>
        <v-alert
          v-else-if="has_operation_error"
          class="mx-2"
          type="error"
        >
          {{ operation_error }}
        </v-alert>
        <v-progress-linear
          v-if="operation_loading"
          indeterminate
          min-width="300"
        />
        <v-divider />
        <v-card-actions class="justify-center pb-4 mt-3 mx-1">
          <v-btn
            color="primary"
            @click="operation_open = false"
          >
            Cancel
          </v-btn>
          <v-spacer />
          <v-btn
            color="success"
            @click="applySubModalAction"
          >
            Apply
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import kraken from '@/components/kraken/KrakenManager'
import { Manifest, ManifestSource } from '@/types/kraken'

export default Vue.extend({
  name: 'ExtensionSettingsModal',
  props: {
    value: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      settings_open: false,
      operation_open: false,
      operation_loading: false,
      operation_error: undefined as string | undefined,
      is_operation_url_invalid: false,
      should_bypass_validate: false,
      source_name: '',
      source_url: '',
      source_enabled: true,
      allow_deduct_name: true,
      editing_source: undefined as Manifest | undefined,
      manifests: [] as Manifest[],
    }
  },
  computed: {
    is_editing(): boolean {
      return this.editing_source !== undefined
    },
    is_factory(): boolean {
      return this.editing_source?.factory ?? false
    },
    has_operation_error(): boolean {
      return this.operation_error !== undefined
    },
  },
  watch: {
    value(val) {
      this.settings_open = val

      if (val) {
        this.fetchManifestsSources()
      }
    },
    settings_open(val) {
      this.$emit('input', val)

      if (!val) {
        this.$emit('refresh')
      }
    },
  },
  methods: {
    order(index: number): string {
      // Based over: https://stackoverflow.com/a/39466341
      return `${index}${['st', 'nd', 'rd'][((index + 90) % 100 - 10) % 10 - 1] || 'th'}`
    },
    blockNameAutoComplete() {
      this.allow_deduct_name = false
    },
    deductNameFromURL() {
      if (!(this.allow_deduct_name && URL.canParse(this.source_url))) {
        return
      }

      const cutPath = new URL(this.source_url).pathname.slice(1)
      if (!cutPath) {
        return
      }
      // This code avoids picking the file identifier as valid name part, it will remove terms like manifest.json etc...
      const parts = cutPath.split('/').filter((part) => !part.endsWith('.json') && !part.endsWith('.txt'))

      this.source_name = `${parts[0] ?? ''} ${parts[1] ?? ''}`.trim()
    },
    clearErrors() {
      this.operation_error = undefined
      this.is_operation_url_invalid = false
    },
    prepareRequest() {
      this.operation_loading = true
      this.clearErrors()
    },
    setDefaultModal() {
      this.clearErrors()

      this.source_name = ''
      this.source_url = ''
      this.source_enabled = true

      this.editing_source = undefined
      this.allow_deduct_name = true

      this.should_bypass_validate = false
    },
    setEditingModal(manifest: Manifest) {
      this.clearErrors()

      this.source_name = manifest.name
      this.source_url = manifest.url
      this.source_enabled = manifest.enabled

      this.editing_source = manifest
      this.allow_deduct_name = false

      this.should_bypass_validate = false

      this.operation_open = true
    },
    setCreateModal() {
      this.setDefaultModal()

      this.operation_open = true
    },
    async applySubModalAction() {
      // The following code can mutate the is_operation_url_invalid property, this is why is not using a defensive
      // approach
      if (this.is_editing) {
        if (this.is_factory) {
          await this.setSourceEnable(this.editing_source!.identifier, this.source_enabled)
        } else {
          await this.updateSource(
            this.editing_source!.identifier,
            this.source_name,
            this.source_url,
            this.source_enabled,
          )
        }
      } else {
        await this.addSource(this.source_name, this.source_url, this.source_enabled)
      }

      // Close the sub modal because errors will also be shown in the main modal, but if URL is invalid we should keep
      // the modal open to allow the user to bypass the validation
      this.operation_open = this.is_operation_url_invalid || false
    },
    async fetchManifestsSources() {
      this.prepareRequest()

      try {
        this.manifests = await kraken.fetchManifestSources(false)
      } catch (error) {
        this.operation_error = `Unable to fetch manifest sources: ${error}`
      } finally {
        this.operation_loading = false
      }
    },
    async addSource(name: string, url: string, enabled: boolean) {
      this.prepareRequest()

      try {
        const source = { name, url, enabled } as ManifestSource
        await kraken.addManifestSource(source, !this.should_bypass_validate)

        this.fetchManifestsSources()
      } catch (error) {
        if (error.response?.status === 502) {
          this.is_operation_url_invalid = true
          return
        }

        this.operation_error = `Unable to add manifest source: ${error}`
      } finally {
        this.operation_loading = false
      }
    },
    async removeSource(identifier: string) {
      this.prepareRequest()

      try {
        await kraken.deleteManifestSource(identifier)

        this.fetchManifestsSources()
      } catch (error) {
        this.operation_error = `Unable to remove manifest source: ${error}`
      } finally {
        this.operation_loading = false
      }
    },
    async updateSource(identifier: string, name: string, url: string, enabled: boolean) {
      this.prepareRequest()

      try {
        const source = { name, url, enabled } as ManifestSource
        await kraken.updateManifestSource(identifier, source, !this.should_bypass_validate)

        this.fetchManifestsSources()
      } catch (error) {
        if (error.response?.status === 502) {
          this.is_operation_url_invalid = true
          return
        }

        this.operation_error = `Unable to update manifest source: ${error}`
      } finally {
        this.operation_loading = false
      }
    },
    async reorderSources() {
      this.prepareRequest()

      const ids = this.manifests.map((manifest) => manifest.identifier)
      try {
        await kraken.setManifestSourcesOrders(ids)

        // After some successful apply we should close the main modal to keep consistency
        this.settings_open = false
      } catch (error) {
        this.operation_error = `Unable to update order: ${error}`
      } finally {
        this.operation_loading = false
      }
    },
    async setSourceEnable(identifier: string, enable: boolean) {
      this.prepareRequest()

      try {
        await (enable ? kraken.enabledManifestSource(identifier) : kraken.disabledManifestSource(identifier))

        this.fetchManifestsSources()
      } catch (error) {
        this.operation_error = `Unable to ${enable ? 'enable' : 'disable'} source: ${error}`
      } finally {
        this.operation_loading = false
      }
    },
  },
})
</script>

<style scoped>
.disabled-source-name {
  position: relative;
  display: inline-block;
}

.disabled-source-name-text {
  opacity: 0.7;
  position: relative;
  z-index: 1;
}

.disabled-source-name::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  border-top: 0.15rem solid currentcolor;
  z-index: 0;
}
</style>
