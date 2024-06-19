<template>
  <v-card
    v-if="tab === 2"
    class="main-container d-flex pa-5"
    text-align="center"
  >
    <div v-if="tab === 2" class="installed-extensions-container">
      <installed-extension-card
        v-for="extension in installed_extensions"
        :key="extension.docker"
        :extension="extension"
        :loading="extension.loading"
        :metrics="metricsFor(extension)"
        :container="getContainer(extension)"
        :versions="remoteVersions(extension)"
        :extension-data="remoteVersions(extension)"
        class="installed-extension-card"
        @edit="openEditDialog"
        @showlogs="showLogs(extension)"
        @uninstall="uninstall(extension)"
        @disable="disable(extension)"
        @enable="enableAndStart(extension)"
        @restart="restart(extension)"
        @update="update"
      />
    </div>
    <template
      v-if="Object.keys(installed_extensions).isEmpty()"
    >
      <p v-if="dockers_fetch_failed" class="text-h6" style="margin: auto;">
        Failed to fetch installed extensions. Make sure the vehicle has internet access and try again.
      </p>
      <p
        v-else-if="dockers_fetch_done"
        class="text-h6"
      >
        No Extensions installed.
      </p>
      <template v-else>
        <spinning-logo size="20%" subtitle="Fetching installed extensions" />
      </template>
    </template>
    <v-fab-transition>
      <v-btn
        :key="'create_button'"
        color="primary"
        fab
        large
        dark
        fixed
        bottom
        right
        class="v-btn--example"
        @click="openCreationDialog"
      >
        <v-icon>mdi-plus</v-icon>
      </v-btn>
    </v-fab-transition>
    <creation-dialog
      v-if="edited_extension"
      :extension="edited_extension"
      @extensionChange="createOrUpdateExtension"
      @closed="clearEditedExtension"
    />
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { ExtensionData } from '@/types/kraken'

export default Vue.extend({
  name: 'InstalledExtensionsTab',
  props: {
    extension: {
      type: Object as PropType<ExtensionData>,
      required: true,
    },
  },
  computed: {
    isCompatible(): boolean {
      return this.extension.is_compatible ?? true
    },
  },
})
</script>

<style scoped>

</style>
