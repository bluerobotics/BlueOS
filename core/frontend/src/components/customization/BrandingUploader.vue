<template>
  <v-card outlined class="pa-3">
    <div class="d-flex align-center">
      <v-avatar tile size="64" class="branding-avatar mr-3">
        <v-img v-if="preview_url" :src="preview_url" contain />
        <v-icon v-else>
          mdi-image-off-outline
        </v-icon>
      </v-avatar>
      <div class="flex-grow-1">
        <div v-if="preview_url" class="text-body-2">
          <a :href="preview_url" target="_blank" rel="noopener noreferrer">
            {{ preview_url.split('?')[0].split('/').pop() }}
          </a>
        </div>
        <div v-else class="text-caption text--secondary">
          {{ emptyLabel }}
        </div>
        <div v-if="asset?.size_bytes" class="text-caption text--secondary">
          {{ format_size(asset.size_bytes) }}
        </div>
      </div>
    </div>
    <div class="d-flex justify-end mt-2">
      <v-btn
        v-tooltip="'Upload a new file'"
        outlined
        small
        color="primary"
        :loading="uploading"
        @click="trigger_picker"
      >
        <v-icon left small>
          mdi-upload
        </v-icon>
        {{ uploadLabel }}
      </v-btn>
      <v-btn
        v-if="preview_url"
        v-tooltip="'Remove the custom file'"
        outlined
        small
        color="error"
        class="ml-2"
        @click="$emit('remove')"
      >
        <v-icon left small>
          mdi-trash-can
        </v-icon>
        Remove
      </v-btn>
    </div>
    <label class="d-none">
      Upload file
      <input
        ref="file_input"
        type="file"
        :accept="accept"
        @change="on_file_change"
      >
    </label>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { BrandingAsset } from '@/types/customization'
import { prettifySize } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'BrandingUploader',

  props: {
    asset: {
      type: Object as PropType<BrandingAsset | null>,
      default: null,
    },
    previewUrl: {
      type: String,
      default: '',
    },
    accept: {
      type: String,
      default: 'image/*',
    },
    uploading: {
      type: Boolean,
      default: false,
    },
    emptyLabel: {
      type: String,
      default: 'No file uploaded.',
    },
    uploadLabel: {
      type: String,
      default: 'Upload',
    },
  },

  computed: {
    preview_url(): string {
      return this.previewUrl || this.asset?.url || ''
    },
  },

  methods: {
    format_size(bytes: number): string {
      return prettifySize(bytes / 1024)
    },

    trigger_picker(): void {
      const input = this.$refs.file_input as HTMLInputElement | undefined
      input?.click()
    },

    on_file_change(event: Event): void {
      const input = event.target as HTMLInputElement
      const file = input.files?.[0]
      if (file) {
        this.$emit('upload', file)
      }
      input.value = ''
    },
  },
})
</script>

<style scoped>
.branding-avatar {
  background-color: rgba(0, 0, 0, 0.04);
}
</style>
