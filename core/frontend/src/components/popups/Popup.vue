<template>
  <vue-final-modal
    v-model="open"
    :click-to-close="options.allowClickToClose ?? true"
    :esc-to-close="options.allowEscToClose ?? true"
    :prevent-click="options.preventClick ?? false"
    :z-index-base="zIndexBase"
    classes="modal-container"
    content-class="modal-content"
    @before-close="onBeforeClose"
  >
    <v-card>
      <v-card-title class="justify-space-between text-h5">
        <span>{{ options.title }}</span>
        <v-icon
          v-if="options.showCloseButton ?? true"
          icon
          @click="dismiss()"
        >
          mdi-close
        </v-icon>
      </v-card-title>
      <v-card-title
        v-if="icon"
        class="justify-center"
      >
        <v-icon
          color="white"
          size="45"
        >
          {{ icon }}
        </v-icon>
      </v-card-title>
      <v-card-subtitle
        class="mt-1"
      >
        {{ options.text }}
      </v-card-subtitle>
      <v-card-actions class="justify-center">
        <v-btn
          v-if="options.showCancelButton ?? true"
          class="ma-2 elevation-2"
          color="grey"
          text
          @click="cancel()"
        >
          {{ options.cancelButtonText ?? 'Cancel' }}
        </v-btn>
        <v-btn
          v-if="options.showConfirmButton ?? true"
          class="ma-2 elevation-2"
          color="primary"
          text
          @click="confirm()"
        >
          {{ options.confirmButtonText ?? 'Confirm' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </vue-final-modal>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { PopupOptions, PopupResult } from '@/types/popups'

export default Vue.extend({
  name: 'Popup',
  props: {
    identifier: {
      type: String,
      required: true,
    },
    options: {
      type: Object as PropType<PopupOptions>,
      required: true,
    },
    dismissed: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      open: true,
      resolved: false,
    }
  },
  computed: {
    icon(): false | string {
      switch (this.options.icon) {
        case 'info':
          return 'mdi-information'
        case 'success':
          return 'mdi-check-circle'
        case 'warning':
          return 'mdi-alert-octagon'
        case 'error':
          return 'mdi-close-circle'
        case 'question':
          return 'mdi-help-circle'
        default:
          return false
      }
    },
    zIndexBase(): number {
      switch (this.options.priority) {
        case 'low':
          return 10000
        case 'medium':
          return 11000
        case 'high':
          return 12000
        default:
          return 9999
      }
    },
  },
  watch: {
    dismissed(dismissed: boolean): void {
      if (dismissed) {
        this.dismiss()
      }
    },
  },
  methods: {
    resolve(result: PopupResult): void {
      this.open = false
      this.resolved = true

      setTimeout(() => {
        this.$emit('resolve', result)
      }, 300)
    },
    confirm(): void {
      this.resolve({
        id: this.identifier,
        confirmed: true,
        canceled: false,
        dismissed: false,
      })
    },
    cancel(): void {
      this.resolve({
        id: this.identifier,
        confirmed: false,
        canceled: true,
        dismissed: false,
      })
    },
    dismiss(): void {
      this.resolve({
        id: this.identifier,
        confirmed: false,
        canceled: false,
        dismissed: true,
      })
    },
    onBeforeClose(): void {
      if (!this.resolved) {
        this.resolve({
          id: this.identifier,
          confirmed: false,
          canceled: false,
          dismissed: true,
        })
      }
    },
  },
})
</script>

<style scoped>
::v-deep .modal-container {
  display: flex;
  justify-content: center;
  align-items: center;
}
::v-deep .modal-content {
  position: relative;
  display: flex;
  flex-direction: column;
  max-height: 90%;
  margin: 0 1rem;
  padding: 1rem;
  border-radius: 0.25rem;
}
</style>
