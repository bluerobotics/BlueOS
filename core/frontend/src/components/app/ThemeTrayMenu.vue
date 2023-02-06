<template>
  <v-icon
    height="100%"
    color="white"
    title="Change theme between dark and light mode."
    @click="toggleDarkTheme"
  >
    {{ settings.is_dark_theme ? 'mdi-weather-night' : 'mdi-white-balance-sunny' }}
  </v-icon>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'

export default Vue.extend({
  name: 'ThemeTrayMenu',
  data: () => ({
    settings,
  }),
  methods: {
    toggleDarkTheme(): void {
      settings.is_dark_theme = !settings.is_dark_theme
    },
  },
})
</script>
