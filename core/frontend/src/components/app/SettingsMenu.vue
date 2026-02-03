<template>
  <v-container
    id="settings-menu-button"
    class="d-flex justify-center"
  >
    <v-btn
      v-tooltip="'Open Settings'"
      class="mr-2"
      icon
      large
      elevation="2"
      @click="openSettings"
    >
      <v-icon>mdi-cog</v-icon>
    </v-btn>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'SettingsMenu',

  methods: {
    openSettings(): void {
      this.$router.push('/settings')
    },
  },
})
</script>
