<template>
  <v-card
    class="mx-auto"
    height="auto"
    width="300"
    outlined
    style="cursor: pointer;"
    :class="{ 'disabled-card': !isCompatible }"
    @click="$emit('clicked')"
  >
    <v-tooltip bottom :disabled="isCompatible">
      <template #activator="{ on, attrs }">
        <v-list-item
          three-line
          v-bind="attrs"
          v-on="on"
        >
          <v-list-item-avatar
            tile
            size="50"
          >
            <v-img contain :src="extension.extension_logo" />
          </v-list-item-avatar>
          <v-list-item-content>
            <v-list-item-title
              class="text-h5 mb-1 extension-name"
              style="font-size: 18px !important;"
            >
              {{ extension.name }}
            </v-list-item-title>
            <v-list-item-subtitle> {{ extension.description }} </v-list-item-subtitle>
            <div
              v-if="!isCompatible"
              class="d-flex justify-left align-center mt-2"
            >
              <v-chip
                v-for="arch in compatibleArchs"
                :key="arch"
                class="mr-1"
                density="compact"
                size="x-small"
              >
                {{ arch }}
              </v-chip>
            </div>
          </v-list-item-content>
        </v-list-item>
      </template>
      <span>This extension is not compatible with current machine architecture running BlueOS.</span>
    </v-tooltip>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { ExtensionData } from '@/types/kraken'

export default Vue.extend({
  name: 'ExtensionCard',
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
    compatibleArchs(): string[] {
      const archs = [
        ...new Set(
          Object.values(this.extension.versions)
            .flatMap((version) => version.images)
            .flatMap((image) => image.platform.architecture),
        ),
      ]

      return archs
    },
  },
})
</script>

<style scoped>
.disabled-card {
  opacity: 0.5;
  position: relative;
}
.disabled-card::before {
  opacity: 1;
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    135deg,
    rgba(255, 255, 255, 0),
    rgba(255, 255, 255, 0) 15px,
    rgba(100, 85, 85, 0.4) 10px,
    rgba(100, 85, 85, 0.4) 16px
  );
  pointer-events: none;
}
</style>
