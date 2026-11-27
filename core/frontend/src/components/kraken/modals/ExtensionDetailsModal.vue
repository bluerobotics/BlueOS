<template>
  <v-card>
    <v-card-subtitle class="px-4 pt-4 pb-2 d-flex justify-space-between align-start">
      <v-avatar size="100" class="extension-icon">
        <v-img contain :src="extension.extension_logo" />
      </v-avatar>
      <div class="extension-creators">
        <div class="extension-title my-2">
          {{ extension.name }}
        </div>
        <div class="extension-description">
          {{ extension.description }}
        </div>
        <div class="extension-architectures">
          <strong>{{ compatible_version_archs.join(', ') }}</strong>
        </div>
      </div>
      <v-btn
        v-if="extension.website"
        v-tooltip="'Homepage'"
        icon
        :href="extension.website"
        target="_blank"
        rel="noopener"
      >
        <v-icon small>
          mdi-web
        </v-icon>
      </v-btn>
    </v-card-subtitle>
    <div class="px-4 pt-4 d-flex justify-space-between align-start">
      <v-select
        v-model="selected_version"
        :items="available_tags"
        :label="t`Version`"
        outlined
        dense
        class="mr-2"
      >
        <template #item="{ item }">
          <v-tooltip :disabled="item.active" bottom>
            <template #activator="{ on, attrs }">
              <div
                style="width: 100%;"
                :style="item.active ? '' : 'opacity: 0.5;'"
                v-bind="attrs"
                v-on="on"
              >
                <v-list-item-content>
                  <v-list-item-title
                    :style="item.value === installed ? { color: 'var(--v-success-darken1)' } : {}"
                    v-text="item.value === installed ? `${item.text} (Active)` : item.text"
                  />
                </v-list-item-content>
              </div>
            </template>
            <span>{{ t`This version is not compatible with current machine running BlueOS` }}</span>
          </v-tooltip>
        </template>
      </v-select>
      <v-tooltip :disabled="extension.is_compatible" bottom>
        <template #activator="{ on, attrs }">
          <v-btn
            :disabled="!extension.is_compatible || !is_version_compatible"
            width="120px"
            height="40px"
            :color="is_installed ? 'error' : 'primary'"

            v-bind="attrs"
            v-on="on"
            @click="performAction"
          >
            {{ is_installed ? t`Uninstall` : t`Install` }}
          </v-btn>
        </template>
        <span>{{ t`No versions available for this architecture` }}</span>
      </v-tooltip>
    </div>
    <v-divider />
    <v-expansion-panels>
      <v-expansion-panel>
        <v-expansion-panel-header class="d-flex justify-space-between">
          <div class="d-flex align-center">
            <v-avatar class="mr-3" size="30" rounded="0">
              <v-img contain :src="extension.company_logo" />
            </v-avatar>
            <!-- eslint-disable-next-line vue/no-v-html, max-len -->
            <span v-html="t`Developed by <strong>${escapeHtml(selected?.company?.name)}</strong>`" />
          </div>
          <template #actions>
            <v-icon>mdi-chevron-down</v-icon>
          </template>
        </v-expansion-panel-header>
        <v-expansion-panel-content>
          <v-card-text>
            {{ t`Written by:` }}
            <ul>
              <li
                v-for="author in (selected?.authors ?? [])"
                :key="author.email"
              >
                {{ author.name }} &#60;{{ author.email }}>
              </li>
            </ul>
          </v-card-text>
        </v-expansion-panel-content>
      </v-expansion-panel>
      <v-expansion-panel>
        <v-expansion-panel-header class="d-flex justify-space-between">
          <div class="d-flex align-center">
            <v-icon class="mr-3" color="primary" size="30">
              mdi-shield-account
            </v-icon>
            <span>{{ t`Permissions` }}</span>
            <v-tooltip
              v-if="is_reset_editing_permissions_visible"
              bottom
            >
              <template #activator="{ on, attrs }">
                <v-icon
                  class="ml-4"
                  v-bind="attrs"
                  v-on="on"
                >
                  mdi-alert
                </v-icon>
              </template>
              <p>{{ t`You are using a custom docker configuration` }}</p>
            </v-tooltip>
          </div>
        </v-expansion-panel-header>
        <v-expansion-panel-content>
          <v-card
            outlined
            width="100%"
            height="300"
          >
            <v-card-text
              v-if="typeof editing_permissions === 'string'"
              style="overflow: auto;"
            >
              <pre>{{ editing_permissions }}</pre>
            </v-card-text>
            <json-editor
              v-else
              v-model="editing_permissions"
              :read-only="is_installed"
              style="width:100%; height:100%"
              @save="onEditingPermissionsSave"
            >
              <template
                v-if="is_reset_editing_permissions_visible"
                #controls
              >
                <v-btn
                  v-tooltip="t`Reset to default permissions`"
                  class="editor-control"
                  icon
                  color="white"
                  @click="onResetToDefaultPermissions"
                >
                  <v-icon>mdi-restore</v-icon>
                </v-btn>
              </template>
            </json-editor>
          </v-card>
        </v-expansion-panel-content>
      </v-expansion-panel>
    </v-expansion-panels>
    <v-card-text class="mt-5">
      <!-- This is a compiled markdown we compile ourselves. it should be safe -->
      <!-- eslint-disable -->
      <v-progress-linear
        v-if="readme_loading"
        indeterminate
      />
      <div
        v-else
        class="readme"
        v-html="compiled_markdown"
      />
      <!-- eslint-enable -->
      <v-btn
        v-if="readme_error && !readme_loading"
        class="mt-2"
        color="primary"
        small
        @click="loadReadme"
      >
        {{ t`Retry` }}
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import { marked } from 'marked'
import { compare } from 'semver'
import { t } from 'ttag'
import Vue, { PropType } from 'vue'

import JsonEditor from '@/components/common/JsonEditor.vue'
import kraken from '@/components/kraken/KrakenManager'
import ReadmeLoader from '@/components/kraken/readmeLoader'
import { JSONValue } from '@/types/common'
import { ExtensionData, InstalledExtensionData, Version } from '@/types/kraken'

export default Vue.extend({
  name: 'ExtensionModal',
  components: {
    JsonEditor,
  },
  props: {
    extension: {
      type: Object as PropType<ExtensionData>,
      required: true,
    },
    installed: {
      type: String,
      default: null,
      required: false,
    },
    installedExtension: {
      type: Object as PropType<InstalledExtensionData>,
      default: null,
      required: false,
    },
  },
  data() {
    return {
      selected_version: '' as string | undefined,
      editing_permissions: '' as string | JSONValue,
      custom_permissions: {} as Record<string, JSONValue>,
      readmes: {} as Record<string, string>,
      readme_loading: false,
      readme_error: false,
      readme_loader: undefined as ReadmeLoader | undefined,
    }
  },
  computed: {
    readme_key(): string {
      return `${this.extension.identifier}:${this.selected_version}`
    },
    selected(): Version | null {
      return this.selected_version ? this.extension.versions[this.selected_version] : null
    },
    compiled_markdown(): string {
      const readme = this.selected?.readme ?? this.readmes[this.readme_key]
      if (!readme) {
        return this.readme_error ? t`Failed to load readme` : t`No readme available`
      }
      // TODO: make sure we sanitize this
      return marked(readme)
    },
    available_tags(): {text: string, value: string, active: boolean}[] {
      const tags = this.getSortedTags().map((tag) => ({
        text: tag,
        value: tag,
        active: this.extension?.versions[tag].images.some((image) => image.compatible),
      }))

      return tags
    },
    is_installed(): boolean {
      return this.selected_version === this.installed
    },
    is_version_compatible(): boolean {
      return this.selected?.images.some((image) => image.compatible) ?? false
    },
    compatible_version_archs(): string[] {
      return [
        ...new Set(
          this.selected
            ?.images.map((image) => image.platform.architecture),
        ),
      ]
    },
    is_reset_editing_permissions_visible(): boolean {
      if (!this.selected_version) {
        return false
      }

      return JSON.stringify(this.editing_permissions) !== JSON.stringify(this.selected?.permissions)
    },
  },
  watch: {
    extension(extension: ExtensionData, previous: ExtensionData) {
      if (extension?.identifier !== previous?.identifier) {
        this.readme_error = false
        this.readme_loading = false
        this.readmes = {}
      }
      this.selected_version = this.getLatestTag()
      this.editing_permissions = this.getVersionPermissions()
      this.custom_permissions = {}
    },
    selected_version() {
      this.editing_permissions = this.getVersionPermissions()
    },
    readme_key() {
      this.loadReadme()
    },
  },
  created() {
    this.readme_loader = new ReadmeLoader({
      has: (key) => key in this.readmes,
      store: (key, readme) => this.$set(this.readmes, key, readme),
      setLoading: (loading) => { this.readme_loading = loading },
      setError: (error) => { this.readme_error = error },
    })
  },
  mounted() {
    this.selected_version = this.getLatestTag()
  },
  methods: {
    async loadReadme(): Promise<void> {
      if (!this.selected_version || this.selected?.readme) {
        this.readme_loading = false
        this.readme_error = false
        return
      }
      const { identifier } = this.extension
      const tag = this.selected_version
      await this.readme_loader?.load(
        this.readme_key,
        () => kraken.fetchExtensionReadme(identifier, tag),
      )
    },
    getSortedTags(): string[] {
      return Object.keys(this.extension.versions).sort((a, b) => compare(b, a))
    },
    getLatestTag(): string {
      return this.getSortedTags()[0] ?? ''
    },
    getVersionPermissions(): string | JSONValue {
      if (!this.selected_version) {
        return 'Select a version to view permissions'
      }

      if (
        this.is_installed
        && this.installedExtension
        && this.installedExtension.user_permissions !== ''
      ) {
        return JSON.parse(this.installedExtension.user_permissions)
      }

      if (this.selected) {
        return this.custom_permissions[this.selected_version] ?? this.selected.permissions
      }

      return 'No permissions required'
    },
    onEditingPermissionsSave(json: JSONValue) {
      if (this.selected_version) {
        this.editing_permissions = json
        this.custom_permissions[this.selected_version] = json
      }
    },
    onResetToDefaultPermissions() {
      if (this.selected_version) {
        delete this.custom_permissions[this.selected_version]
        this.editing_permissions = this.getVersionPermissions()
      }
    },
    performAction() {
      if (!this.selected_version) {
        return
      }

      this.$emit(
        'clicked',
        this.extension.identifier,
        this.selected_version,
        JSON.stringify(this.custom_permissions[this.selected_version]),
        this.is_installed,
      )
    },
  },
})
</script>
<style>
div.readme {
  line-height: 200%;
}
div.readme p {
  margin-top: 10px;
  margin-left: 20px;
}
div.readme pre {
  margin-left: 20px;
}
div.readme h1 {
  margin-bottom: 20px;
}

div.readme h2 {
  margin-bottom: 10px;
  margin-left: 10px;
}

div.readme h3 {
  margin-bottom: 10px;
  margin-left: 20px;
}

div.readme ul {
  margin-left: 20px;
}

div.readme img {
  max-width: 100%;
}

.editor-control {
  margin: 0;
  opacity: 0.7;
}

.extension-creators {
  flex-grow: 1;
  margin-left: 10px;
}
.extension-title {
  font-weight: bold;
  font-size: 30px;
}
.extension-description {
  color: gray;
  font-size: 14px;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  text-overflow: ellipsis;
}
.extension-architectures {
  color: gray;
  font-size: 15px;
  padding-top: 4px;
  text-transform: uppercase;
}
.extension-icon {
  border-radius: 13px !important;
  overflow: hidden;
}
</style>
