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
                />
              </v-col>

              <v-col class="text-center">
                <v-btn
                  v-if="installed === selected_version"
                  class="mt-3"
                  disabled
                  color="primary"
                >
                  Installed
                </v-btn>
                <v-btn
                  v-else
                  class="mt-3"
                  color="primary"
                  @click="$emit('clicked', selected_version, selected_id)"
                >
                  Install
                </v-btn>
              </v-col>
            </v-row>
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
      selected_id: undefined as string | undefined,
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
    available_tags(): string[] {
      return Object.keys(this.extension?.versions ?? [])
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
  },
  watch: {
    extension() {
      const [first] = Object.keys(this.extension.versions) ?? ''
      this.selected_version = first
      this.selected_id = this.extension.versions[this.selected_version].id
      console.log(this.selected_id)
    },
  },
  mounted() {
    const [first] = Object.keys(this.extension.versions) ?? ''
    this.selected_version = first
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
