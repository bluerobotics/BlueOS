<template>
  <div>
    <v-row align="center" no-gutters class="customization-header" @click="expanded = !expanded">
      <v-col cols="12" sm="8">
        <div class="d-flex align-center">
          <v-avatar color="primary" size="48" class="mr-4">
            <v-icon color="white" size="28">
              mdi-palette-swatch
            </v-icon>
          </v-avatar>
          <div>
            <div class="text-subtitle-1 font-weight-medium">
              Customization
            </div>
            <div class="text-caption text--secondary">
              Theme color, 3D models, logo and vehicle image
            </div>
          </div>
        </div>
      </v-col>
      <v-col cols="12" sm="4" class="text-sm-right mt-3 mt-sm-0">
        <v-btn icon>
          <v-icon>{{ expanded ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
        </v-btn>
      </v-col>
    </v-row>

    <v-expand-transition>
      <div v-if="expanded" class="mt-4">
        <v-divider class="mb-4" />

        <div class="text-subtitle-2 mb-2">
          Primary color
        </div>
        <v-row align="center" no-gutters class="mb-2">
          <v-col cols="12" sm="6">
            <div v-if="theme_primary" class="d-flex align-center">
              <v-menu
                v-model="color_menu"
                :close-on-content-click="false"
                offset-y
              >
                <template #activator="{ on, attrs }">
                  <div
                    class="color-swatch mr-3"
                    :style="{ backgroundColor: theme_primary }"
                    v-bind="attrs"
                    v-on="on"
                  />
                </template>
                <v-card>
                  <v-color-picker
                    v-model="theme_primary"
                    mode="hex"
                    hide-mode-switch
                    show-swatches
                  />
                </v-card>
              </v-menu>
              <div>
                <div class="text-body-2">
                  {{ theme_primary }}
                </div>
                <div class="text-caption text--secondary">
                  Drives the gradient and scrollbar
                </div>
              </div>
            </div>
            <div v-else class="text-caption text--secondary">
              Loading current theme...
            </div>
          </v-col>
          <v-col cols="12" sm="6" class="text-sm-right mt-3 mt-sm-0">
            <v-btn
              v-tooltip="'Save the chosen color and regenerate the theme CSS'"
              outlined
              small
              color="primary"
              :loading="theme_saving"
              :disabled="!theme_primary || theme_primary === theme_status?.primary"
              @click="save_theme"
            >
              <v-icon left small>
                mdi-content-save
              </v-icon>
              Apply
            </v-btn>
            <v-btn
              v-tooltip="'Restore the default BlueOS theme'"
              outlined
              small
              class="ml-2"
              :loading="theme_resetting"
              @click="reset_theme"
            >
              <v-icon left small>
                mdi-restore
              </v-icon>
              Reset
            </v-btn>
          </v-col>
        </v-row>

        <div v-if="palette_entries.length" class="d-flex mb-4">
          <div
            v-for="entry in palette_entries"
            :key="entry.name"
            v-tooltip="`${entry.name}: ${entry.color}`"
            class="palette-chip"
            :style="{ backgroundColor: entry.color }"
          />
        </div>

        <v-divider class="my-4" />

        <div class="text-subtitle-2 mb-2">
          3D model overrides
        </div>
        <v-row align="center" no-gutters class="mb-2">
          <v-col cols="12" sm="8">
            <div class="text-caption text--secondary">
              Upload <code>.glb</code> files served at
              <code>/userdata/modeloverrides/</code>. Use a relative name like
              <code>sub/MyFrame.glb</code> or <code>ALL.glb</code> to override every vehicle.
            </div>
          </v-col>
          <v-col cols="12" sm="4" class="text-sm-right mt-3 mt-sm-0">
            <v-btn
              outlined
              small
              color="primary"
              :loading="model_uploading"
              @click="open_model_dialog"
            >
              <v-icon left small>
                mdi-upload
              </v-icon>
              Upload model
            </v-btn>
          </v-col>
        </v-row>

        <v-list v-if="models.length" dense class="model-list">
          <v-list-item v-for="model in models" :key="model.name">
            <v-list-item-icon>
              <v-icon>mdi-cube-outline</v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-title>{{ model.name }}</v-list-item-title>
              <v-list-item-subtitle>
                {{ format_size(model.size_bytes) }}
              </v-list-item-subtitle>
            </v-list-item-content>
            <v-list-item-action>
              <v-btn icon small color="error" @click="delete_model(model)">
                <v-icon small>
                  mdi-trash-can
                </v-icon>
              </v-btn>
            </v-list-item-action>
          </v-list-item>
        </v-list>
        <div v-else class="text-caption text--secondary mb-2">
          No model overrides uploaded.
        </div>

        <v-divider class="my-4" />

        <v-row no-gutters>
          <v-col cols="12" md="6" class="pr-md-2">
            <div class="text-subtitle-2 mb-2">
              Project logo
            </div>
            <branding-uploader
              :asset="logo"
              :preview-url="logo_url"
              accept="image/png,image/jpeg,image/webp,image/gif"
              :uploading="logo_uploading"
              empty-label="No custom logo set."
              upload-label="Upload logo"
              @upload="upload_logo"
              @remove="delete_logo"
            />
          </v-col>
          <v-col cols="12" md="6" class="pl-md-2 mt-4 mt-md-0">
            <div class="text-subtitle-2 mb-2">
              Vehicle image
            </div>
            <branding-uploader
              :asset="vehicle_image"
              :preview-url="vehicle_image_url"
              accept="image/png,image/jpeg,image/webp,image/gif"
              :uploading="vehicle_image_uploading"
              empty-label="No custom vehicle image set."
              upload-label="Upload image"
              @upload="upload_vehicle_image"
              @remove="delete_vehicle_image"
            />
          </v-col>
        </v-row>
      </div>
    </v-expand-transition>

    <v-dialog v-model="model_dialog" max-width="500">
      <v-card>
        <v-card-title>Upload 3D model override</v-card-title>
        <v-card-text>
          <v-file-input
            v-model="model_file"
            accept=".glb"
            label=".glb file"
            prepend-icon="mdi-cube-outline"
            show-size
          />
          <v-text-field
            v-model="model_name"
            label="Destination name"
            placeholder="sub/MyFrame.glb"
            hint="Relative path under modeloverrides/. Defaults to the file name."
            persistent-hint
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn text @click="model_dialog = false">
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            :disabled="!model_file"
            :loading="model_uploading"
            @click="upload_model"
          >
            Upload
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import customization_store from '@/store/customization'
import { BrandingAsset, ModelEntry, ThemeStatus } from '@/types/customization'
import { prettifySize } from '@/utils/helper_functions'

import BrandingUploader from './BrandingUploader.vue'

interface PaletteEntry {
  name: string
  color: string
}

export default Vue.extend({
  name: 'ThemeCustomization',

  components: {
    BrandingUploader,
  },

  data() {
    return {
      expanded: false,
      color_menu: false,
      theme_primary: '',
      model_dialog: false,
      model_file: null as File | null,
      model_name: '',
    }
  },

  computed: {
    theme_status(): ThemeStatus | null {
      return customization_store.themeStatus
    },
    models(): ModelEntry[] {
      return customization_store.models
    },
    logo(): BrandingAsset {
      return customization_store.logo
    },
    logo_url(): string {
      return customization_store.logoUrl ?? ''
    },
    vehicle_image(): BrandingAsset {
      return customization_store.vehicleImage
    },
    vehicle_image_url(): string {
      return customization_store.vehicleImageUrl ?? ''
    },
    theme_saving(): boolean {
      return customization_store.themeSaving
    },
    theme_resetting(): boolean {
      return customization_store.themeResetting
    },
    model_uploading(): boolean {
      return customization_store.modelUploading
    },
    logo_uploading(): boolean {
      return customization_store.logoUploading
    },
    vehicle_image_uploading(): boolean {
      return customization_store.vehicleImageUploading
    },
    palette_entries(): PaletteEntry[] {
      const palette = this.theme_status?.palette ?? {}
      return Object.entries(palette).map(([name, color]) => ({ name, color }))
    },
  },

  watch: {
    expanded(value: boolean) {
      if (value) {
        customization_store.refreshAll()
      }
    },
    theme_status: {
      immediate: true,
      handler(value: ThemeStatus | null) {
        if (value?.primary) {
          this.theme_primary = value.primary
        }
      },
    },
  },

  mounted() {
    // Eagerly load so theme_primary reflects the saved value even before the
    // user expands the panel; otherwise the swatch could lie about the truth.
    customization_store.refreshAll()
  },

  methods: {
    format_size(bytes: number | null): string {
      if (bytes === null) return ''
      return prettifySize(bytes / 1024)
    },

    save_theme(): Promise<void> {
      return customization_store.saveTheme(this.theme_primary)
    },

    reset_theme(): Promise<void> {
      // eslint-disable-next-line no-alert
      if (!window.confirm('Reset the theme to defaults?')) {
        return Promise.resolve()
      }
      return customization_store.resetTheme()
    },

    open_model_dialog(): void {
      this.model_file = null
      this.model_name = ''
      this.model_dialog = true
    },

    async upload_model(): Promise<void> {
      if (!this.model_file) return
      const name = this.model_name.trim() || this.model_file.name
      await customization_store.uploadModel({ file: this.model_file, name })
      this.model_dialog = false
    },

    delete_model(model: ModelEntry): Promise<void> {
      // eslint-disable-next-line no-alert
      if (!window.confirm(`Delete the model override "${model.name}"? This cannot be undone.`)) {
        return Promise.resolve()
      }
      return customization_store.deleteModel(model.name)
    },

    upload_logo(file: File): Promise<void> {
      return customization_store.uploadLogo(file)
    },

    delete_logo(): Promise<void> {
      // eslint-disable-next-line no-alert
      if (!window.confirm('Remove the custom logo?')) {
        return Promise.resolve()
      }
      return customization_store.deleteLogo()
    },

    upload_vehicle_image(file: File): Promise<void> {
      return customization_store.uploadVehicleImage(file)
    },

    delete_vehicle_image(): Promise<void> {
      // eslint-disable-next-line no-alert
      if (!window.confirm('Remove the custom vehicle image?')) {
        return Promise.resolve()
      }
      return customization_store.deleteVehicleImage()
    },
  },
})
</script>

<style scoped>
.customization-header {
  cursor: pointer;
}

.color-swatch {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  cursor: pointer;
}

.palette-chip {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  margin-right: 6px;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.model-list {
  background: transparent !important;
  max-height: 240px;
  overflow-y: auto;
}
</style>
