<template>
  <v-container>
    <v-card id="welcome-card">
      <v-card-title><p>Welcome to BlueOS!</p></v-card-title>
      <v-card-text>
        <p>
          Before start using, we highly recommend to <a
            href="https://docs.bluerobotics.com/ardusub-zola/software/companion/1.0/configuration/#connect-wifi"
          >
            connect first on the internet
          </a>
          and do the
          <a href="https://docs.bluerobotics.com/ardusub-zola/software/companion/1.0/configuration/#select-version">
            system update to the latest version available
          </a>
          .
        </p>
        <v-card-text />
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'Main',
})
</script>
