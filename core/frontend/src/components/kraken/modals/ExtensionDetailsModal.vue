<template>
  <v-card>
    <v-card-subtitle class="px-4 pt-4 pb-2 d-flex justify-space-between align-start">
      <v-avatar size="100" rounded="0">
        <v-img contain :src="extension.extension_logo" />
      </v-avatar>
      <div class="extension-creators">
        <div class="extension-title my-2">
          {{ extension.name }}
        </div>
        <div class="extension-description">
          {{ extension.description }}
        </div>
        <div class="extension-description">
          <strong>{{ compatible_version_archs.join(', ') }}</strong>
        </div>
      </div>
    </v-card-subtitle>
    <div class="px-4 pt-4 d-flex justify-space-between align-start">
      <v-select
        v-model="selected_version"
        :items="available_tags"
        label="Version"
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
                  <v-list-item-title v-text="item.text" />
                </v-list-item-content>
              </div>
            </template>
            <span>This version is not compatible with current machine running BlueOS</span>
          </v-tooltip>
        </template>
      </v-select>
      <v-tooltip :disabled="extension.is_compatible" bottom>
        <template #activator="{ on, attrs }">
          <v-btn
            :disabled="!extension.is_compatible || !is_version_compatible"
            width="120px"
            height="40px"
            color="primary"

            v-bind="attrs"
            v-on="on"
            @click="$emit('clicked', extension.identifier, selected_version, is_installed)"
          >
            {{ is_installed ? 'Uninstall' : 'Install' }}
          </v-btn>
        </template>
        <span>No versions available for this architecture</span>
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
            <span>Developed by <strong>{{ selected?.company?.name }}</strong></span>
          </div>
          <template #actions>
            <v-icon>mdi-chevron-down</v-icon>
          </template>
        </v-expansion-panel-header>
        <v-expansion-panel-content>
          <v-card-text>
            Written by:
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
            <span>Permissions</span>
          </div>
        </v-expansion-panel-header>
        <v-expansion-panel-content>
          <v-card
            v-if="permissions"
            outlined
            width="100%"
          >
            <v-card-text
              style="overflow: auto;"
            >
              <pre>{{ permissions }}</pre>
            </v-card-text>
          </v-card>
        </v-expansion-panel-content>
      </v-expansion-panel>
    </v-expansion-panels>

  </v-card>
</template>

<script lang="ts">
import { marked } from 'marked'
import { compare } from 'semver'
import Vue, { PropType } from 'vue'

import settings from '@/libs/settings'
import { JSONValue } from '@/types/common'
import { ExtensionData, Version } from '@/types/kraken'

export default Vue.extend({
  name: 'ExtensionModal',
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
  },
  data() {
    return {
      selected_version: '' as string | null | undefined,
    }
  },
  computed: {
    selected(): Version | null {
      return this.selected_version ? this.extension.versions[this.selected_version] : null
    },
    is_using_custom_tag(): boolean {
      return this.selected_version === null
    },
    compiled_markdown(): string {
      if (!this.selected?.readme) {
        return 'No readme available'
      }
      // TODO: make sure we sanitize this
      return marked(this.selected.readme)
    },
    available_tags(): {text: string, value: string | null, active: boolean}[] {
      const tags = this.getSortedTags().map((tag) => ({
        text: tag,
        value: tag as string | null,
        active: this.extension?.versions[tag].images.some((image) => image.compatible),
      }))

      if (settings.is_pirate_mode) {
        tags.push({
          text: 'Custom',
          value: null,
          active: true,
        })
      }

      return tags
    },
    permissions(): (undefined | JSONValue) {
      if (!this.selected_version) {
        return 'Select a version'
      }
      const versions = this.extension?.versions
      if (versions && this.selected_version in versions) {
        return versions[this.selected_version].permissions
      }
      return 'No permissions required'
    },
    is_installed(): boolean {
      return this.selected_version === this.installed
    },
    is_version_compatible(): boolean {
      if (this.is_using_custom_tag) {
        return true
      }

      return this.selected?.images.some((image) => image.compatible) ?? false
    },
    compatible_version_archs(): string[] {
      return this.is_using_custom_tag ? [] : [
        ...new Set(
          this.selected
            ?.images.map((image) => image.platform.architecture),
        ),
      ]
    },
  },
  watch: {
    extension() {
      this.selected_version = this.getLatestTag()
    },
  },
  mounted() {
    this.selected_version = this.getLatestTag()
  },
  methods: {
    getSortedTags(): string[] {
      return Object.keys(this.extension.versions).sort((a, b) => compare(b, a))
    },
    getLatestTag(): string {
      return this.getSortedTags()[0] ?? ''
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
}
</style>
