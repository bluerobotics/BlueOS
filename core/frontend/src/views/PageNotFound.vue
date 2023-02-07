<template>
  <div class="d-flex flex-column align-center">
    <v-icon
      style="height: 400px"
      size="256"
      v-text="'mdi-sail-boat-sink'"
    />
    <div
      class="text-h6"
      :v-text="'Vehicle not found.'"
    />
    <p class="text-h6 text-center ma-4">
      Page not found!
    </p>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'NoneViewer',
})
</script>
