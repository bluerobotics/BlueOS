<template>
  <v-dialog
    :value="value"
    :width="width"
    :persistent="persistent"
    @input="emitInput"
    @click:outside="handleOutsideClick"
    @keydown.esc="handleEsc"
  >
    <v-sheet
      color="warning"
      outlined
    >
      <v-card variant="outlined">
        <v-card-title class="align-center">
          <span class="warning-title">
            <span
              class="warning-emoji"
              aria-label="warning"
              role="img"
            >⚠️</span>
            {{ title }}
          </span>
        </v-card-title>
        <v-card-text :class="['warning-text', textClass]">
          {{ message }}
        </v-card-text>
        <v-card-actions>
          <v-btn :color="cancelColor" @click="close">
            {{ cancelLabel }}
          </v-btn>
          <v-spacer />
          <v-btn :color="confirmColor" @click="confirmAndMaybeClose">
            {{ confirmLabel }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-sheet>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

export default Vue.extend({
  name: 'WarningDialog',
  props: {
    value: {
      type: Boolean,
      required: true,
    },
    title: {
      type: String,
      default: 'WARNING',
    },
    message: {
      type: String,
      required: true,
    },
    confirmLabel: {
      type: String,
      required: true,
    },
    cancelLabel: {
      type: String,
      default: 'Cancel',
    },
    confirmColor: {
      type: String as PropType<string>,
      default: 'warning',
    },
    cancelColor: {
      type: String as PropType<string>,
      default: 'primary',
    },
    width: {
      type: [String, Number] as PropType<string | number>,
      default: 'fit-content',
    },
    persistent: {
      type: Boolean,
      default: false,
    },
    closeOnOutside: {
      type: Boolean,
      default: true,
    },
    closeOnEsc: {
      type: Boolean,
      default: true,
    },
    closeOnConfirm: {
      type: Boolean,
      default: true,
    },
    textClass: {
      type: String,
      default: '',
    },
  },
  methods: {
    emitInput(state: boolean) {
      this.$emit('input', state)
    },
    close() {
      this.emitInput(false)
    },
    handleOutsideClick() {
      if (this.closeOnOutside && !this.persistent) {
        this.close()
      }
    },
    handleEsc() {
      if (this.closeOnEsc && !this.persistent) {
        this.close()
      }
    },
    confirmAndMaybeClose() {
      this.$emit('confirm')
      if (this.closeOnConfirm) {
        this.close()
      }
    },
  },
})
</script>

<style scoped>
.warning-title {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.warning-emoji {
  font-size: 1.2rem;
}

.warning-text {
  max-width: 30rem;
}
</style>
