<template>
  <v-card>
    <v-card-title class="text-h5 grey lighten-2 black--text">
      {{ extension?.name ?? '' }}
    </v-card-title>

    <v-card-text>
      <v-row>
        <v-col
          cols="10"
          sm="8"
          class="mt-5"
        >
          <v-card
            min-height="50vh"
            height="100%"
            rounded="lg"
            style="overflow: auto;"
          >
            <v-card-text>
              <!-- This is a compiled markdown we compile ourselves. it should be safe -->
              <!-- eslint-disable -->
              <div
                class="readme"
                v-html="compiled_markdown"
              />
              <!-- eslint-enable -->
            </v-card-text>
          </v-card>
        </v-col>
        <v-col
          cols="4"
          sm="4"
          class="mt-5"
        >
          <v-sheet
            min-height="50vh"
            rounded="lg"
          >
            <v-row dense>
              <v-col>
                <v-select
                  v-model="selected_version"
                  :items="available_tags"
                  label="Version"
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
              </v-col>
              <v-col class="text-center">
                <v-tooltip :disabled="extension.is_compatible" bottom>
                  <template #activator="{ on, attrs }">
                    <v-btn
                      class="mt-3"
                      :disabled="!extension.is_compatible || !is_version_compatible"
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
              </v-col>
            </v-row>
            <span
              v-if="!extension.is_compatible || !is_version_compatible"
            >
              <h3
                class="ma-2"
              >
                Compatible only with:
              </h3>
              <v-chip
                v-for="arch in compatible_version_archs"
                :key="arch"
                class="mr-1 mb-1"
                density="compact"
                size="x-small"
              >
                {{ arch }}
              </v-chip>
            </span>
            <h3
              v-if="selected?.website"
              class="ma-2"
            >
              Website:
            </h3>
            <a :href="selected?.website">
              {{ selected?.website }}</a>
            <h3
              v-if="selected?.docs"
              class="ma-2"
            >
              Docs:
            </h3>
            <a :href="selected?.docs">
              {{ selected?.docs }}</a>

            <h3
              v-if="permissions"
              class="ma-2"
            >
              Settings:
            </h3>
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
            <span v-if="selected?.company">
              <v-card
                class="mt-2"
                outlined
              >
                <span
                  class="mb-3 align-center"
                  style="display: flex; flex: 1 1 auto;"
                >
                  <v-img
                    class="ma-2"
                    :src="extension.company_logo"
                    max-height="30"
                    max-width="30"
                  />
                  <h3 class="ma-2">
                    {{ selected?.company.name }}
                  </h3>
                </span>
                <v-card-text v-if="selected?.company.about">
                  {{ selected?.company.about }}
                </v-card-text>
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
              </v-card>
            </span>
          </v-sheet>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import { marked } from 'marked'
import { compare } from 'semver'
import Vue, { PropType } from 'vue'

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
      selected_version: '' as string,
    }
  },
  computed: {
    selected(): Version | null {
      return this.selected_version ? this.extension.versions[this.selected_version] : null
    },
    compiled_markdown(): string {
      if (!this.selected?.readme) {
        return 'No readme available'
      }
      // TODO: make sure we sanitize this
      return marked(this.selected.readme)
    },
    available_tags(): {text: string, active: boolean}[] {
      return this.getSortedTags().map((tag) => ({
        text: tag,
        active: this.extension?.versions[tag].images.some((image) => image.compatible),
      }))
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
      return this.extension.versions[this.selected_version]?.images.some((image) => image.compatible)
    },
    compatible_version_archs(): string[] {
      const archs = [
        ...new Set(
          this.extension.versions[this.selected_version]
            ?.images.map((image) => image.platform.architecture),
        ),
      ]

      return archs
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
</style>
