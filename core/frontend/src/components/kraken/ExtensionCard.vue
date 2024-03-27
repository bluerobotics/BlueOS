<template>
  <v-card
    class="mx-auto"
    height="100"
    width="300"
    outlined
    style="cursor: pointer;"
    :class="{ 'disabled-card': !(extension.is_compatible ?? true) }"
    @click="$emit('clicked')"
  >
    <v-tooltip bottom :disabled="extension.is_compatible ?? true">
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
          </v-list-item-content>
        </v-list-item>
        <v-card-subtitle class="pt-0">
          {{ extension.author }}
        </v-card-subtitle>
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
})
</script>

<style scoped>
.disabled-card {
  opacity: 0.8;
}
</style>
