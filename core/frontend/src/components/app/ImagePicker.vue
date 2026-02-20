<template>
  <div id="imgdiv" class="d-flex align-center">
    <v-img
      id="main"
      :height="size"
      :width="size"
      class="shrink"
      contain
      :src="image !== null ? image : defaultImage"
      @click="openDialog()"
    />
    <v-btn
      id="edit-icon"
      class="mx-2"
      fab
      dark
      x-small
      @click="openDialog"
    >
      <v-icon>
        mdi-pencil
      </v-icon>
    </v-btn>
    <v-dialog v-model="dialog" @dragover.prevent @dragenter.prevent @drop.prevent="onDrop">
      <v-card class="pa-2">
        <v-card-title>
          Pick an Image
        </v-card-title>
        <v-row v-if="allimages.length > 0" class="overflow-auto" style="max-height: 500px;" justify="space-around">
          <v-col v-for="(each_image, index) in allimages" :key="index" cols="12" sm="3" md="3">
            <v-card
              :class="{ 'selected-image': selected_index === index }"
              class="image-card"
              @click="selectImage(index)"
            >
              <v-img :src="`${each_image.name}`" contain aspect-ratio="1" />
              <v-btn
                v-if="!each_image.readonly"
                id="trashcan-icon"
                class="mx-2"
                fab
                dark
                x-small
                @click.stop="deleteImage(index)"
              >
                <v-icon>
                  mdi-trash-can
                </v-icon>
              </v-btn>
            </v-card>
          </v-col>
        </v-row>
        <v-row v-else-if="loading">
          <SpinningLogo size="100px" />
        </v-row>
        <v-row v-else>
          <v-alert>
            No images found at {{ directory }}. Please upload some images to this directory using the file browser.
          </v-alert>
          <v-alert v-if="error" color="red lighten-2">
            {{ error }}
          </v-alert>
        </v-row>
        <v-row>
          <v-col cols="12">
            <v-card
              class="drop-zone"
              @dragover.prevent
              @dragenter.prevent
              @drop.prevent="onDrop"
            >
              <v-card-text>
                Drag and drop an image file here to upload
              </v-card-text>
              <input
                id="file-input"
                ref="fileInput"
                aria-label="File browser"
                type="file"
                accept="image/*"
                style="display:none"
                @change="onFileInputChange"
              />
              <v-btn color="primary" @click="onFilePickerClick">
                Click to upload an image
              </v-btn>
            </v-card>
          </v-col>
        </v-row>
        <v-alert v-if="upload_error" color="red lighten-2">
          {{ upload_error }}
        </v-alert>
      </v-card>
    </v-dialog>
  </div>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import back_axios from '@/utils/api'

interface FileEntry {
  name: string;
  type: string;
  mtime: string;
}

interface ImageUrl {
  name: string;
  readonly: boolean;
}

export default Vue.extend({
  name: 'ImagePicker',
  components: {
    SpinningLogo,
  },
  props: {
    size: {
      type: String,
      default: '50',
    },
    directory: {
      type: String,
      default: '/userdata/images/',
      required: false,
    },
    readonlyFiles: {
      type: Array<string>,
      default: () => [],
      required: false,
    },
    defaultImage: {
      type: String,
      default: null,
      required: false,
    },
    image: {
      type: String,
      default: null,
      required: false,
    },
  },
  data() {
    return {
      dialog: false,
      selected_index: null as number | null,
      images: [] as string[],
      error: null as string | null,
      loading: true,
      upload_error: null as string | null,
    }
  },
  computed: {
    allimages(): ImageUrl[] {
      const images = this.images.map((image: string) => (
        { name: `${this.directory}/${image}`, readonly: false }))
      const readonly_images = this.readonlyFiles.map((path: string) => (
        { name: path, readonly: true }))
      return [...images, ...readonly_images, { name: this.defaultImage, readonly: true }]
    },
  },
  mounted() {
    this.loadImages()
  },
  methods: {
    selectImage(index: number) {
      this.selected_index = index
      this.$emit('image-selected', this.allimages[index].name)
      this.dialog = false
    },
    openDialog() {
      this.dialog = true
    },
    loadImages() {
      back_axios({
        method: 'get',
        url: this.directory,
      }).then((response) => {
        this.images = response.data.filter(
          (string: FileEntry) => string.type === 'file',
        ).map((file: FileEntry) => file.name)
        this.loading = false
      }).catch((error) => {
        this.error = error
      })
    },
    async deleteImage(index: number) {
      try {
        await back_axios({
          method: 'delete',
          url: `/upload/${this.directory}/${this.images[index]}`,
        })
        this.loadImages()
      } catch (error) {
        console.error('Error deleting file:', error)
        this.error = `Error deleting file: ${error}`
      }
    },
    onFileInputChange(event: Event) {
      const target = event.target as HTMLInputElement
      const file = target.files?.[0]
      if (!file) return
      const fileName = encodeURIComponent(file.name)
      this.uploadFile(file, `${this.directory}/${fileName}`)
    },
    onFilePickerClick() {
      const input = this.$refs.fileInput as HTMLInputElement
      input.click()
    },
    async uploadFile(file: File, destination_path: string) {
      const config = {
        headers: {
          'Content-Type': file.type,
        },
      }
      await axios.put(`/upload/${destination_path}`, file, config)
        .catch((error) => {
          this.upload_error = error
          console.log(`Error uploading file: ${error}`)
        })
      this.loadImages()
    },
    async onDrop(event: DragEvent) {
      const file = event.dataTransfer?.files?.[0]
      if (!file) return
      const fileName = encodeURIComponent(file.name)
      await this.uploadFile(file, `${this.directory}/${fileName}`)
    },
  },
})
</script>
<style scoped>
  #main {
    display: inline-flex;
    margin: 0;
    object-fit: contain;
    position: relative;
  }

  #edit-icon {
    display: none;
    position: absolute;
    right: -15px;
    bottom: 0;
  }

  #imgdiv:hover #edit-icon{
    display: inline-flex !important;
  }

  #imgdiv {
    position: relative;
  }

  .drop-zone {
    border: 2px dashed #ccc;
    border-radius: 4px;
    text-align: center;
    padding: 20px;
    margin: 20px 0;
  }

  .image-card {
    position: relative;
  }

  #trashcan-icon {
    display: none;
    position: absolute;
    top: -10px;
    right: -10px;
  }

  .image-card:hover #trashcan-icon {
    display: inline-flex !important;
  }

</style>
