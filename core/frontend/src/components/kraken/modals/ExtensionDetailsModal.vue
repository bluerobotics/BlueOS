<template>
  <v-dialog
    v-if="value"
    v-model="show_dialog"
    width="75%"
  >
    <v-card>
      <v-card-subtitle class="px-3 py-2 d-flex justify-space-between align-start">
        <v-avatar size="100" rounded="0">
          <v-img contain :src="value.extension_logo" />
        </v-avatar>
        <div class="extension-creators">
          <div class="extension-title my-2">
            {{ value.name }}
          </div>
          <div class="extension-description">
            {{ value.description }}
          </div>
        </div>
        <!-- Add here the select adn install, make sure if the screen is small to break -->
      </v-card-subtitle>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import { marked } from 'marked'
import Vue, { PropType } from 'vue'

import { getLatestVersion, getSortedVersions } from '@/components/kraken/Utils'
import { JSONValue } from '@/types/common'
import { ExtensionData, InstalledExtensionData, Version } from '@/types/kraken'

export default Vue.extend({
  name: 'ExtensionDetailsModal',
  props: {
    value: {
      type: Object as PropType<ExtensionData>,
      required: false,
      default: undefined,
    },
    installed: {
      type: Array as PropType<InstalledExtensionData[]>,
      required: true,
    },
  },
  data() {
    return {
      show_dialog: false,
      selected_version: '' as string,
    }
  },
  computed: {
    selected(): Version | undefined {
      return this.selected_version ? this.value.versions[this.selected_version] : undefined
    },
    compiled_markdown(): string {
      if (!this.selected?.readme) {
        return 'No readme available'
      }
      // TODO: make sure we sanitize this
      return marked(this.selected.readme)
    },
    available_tags(): {text: string, active: boolean}[] {
      return getSortedVersions(this.value.versions).map((v) => ({
        text: v.tag,
        active: v.images.some((image) => image.compatible),
      }))
    },
    permissions(): (undefined | JSONValue) {
      if (!this.selected_version) {
        return 'Select a version'
      }
      const versions = this.value?.versions
      if (versions && this.selected_version in versions) {
        return versions[this.selected_version].permissions
      }
      return 'No permissions required'
    },
    installed_extension(): InstalledExtensionData | undefined {
      return this.installed.find((installed) => installed.identifier === this.value.identifier)
    },
    is_installed(): boolean {
      return this.installed_extension !== undefined
    },
    is_version_compatible(): boolean {
      return this.selected?.images.some((image) => image.compatible) ?? false
    },
    compatible_version_archs(): string[] {
      const archs = [
        ...new Set(
          this.selected?.images.map((image) => image.platform.architecture),
        ),
      ]

      return archs
    },
  },
  watch: {
    value(val: ExtensionData | undefined) {
      if (val !== undefined) {
        this.show_dialog = true
        this.selected_version = getLatestVersion(val.versions)?.tag ?? ''
      }
    },
    show_dialog(val: boolean) {
      if (!val) {
        this.$emit('input', undefined)
      }
    },
  },
})
</script>
<style>
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
