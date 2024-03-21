<template>
  <div
    style="z-index: 9999;"
  >
    <Popup
      v-for="popup in popups"
      :key="popup.id"
      :identifier="popup.id"
      :options="popup.options"
      :dismissed="popup.dismissed"
      @resolve="popup.resolve"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import popups from '@/store/popups'

import Popup from './Popup.vue'

export default Vue.extend({
  name: 'PopupsManager',
  components: {
    Popup,
  },
  computed: {
    popups() {
      return popups.popup_values
    },
  },
})
</script>

<style>
</style>
