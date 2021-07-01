<template>
  <v-app>
    <v-card
      flat
    >
      <v-app-bar
        color="#08c"
        rounded="0"
      >
        <v-app-bar-nav-icon
          color="white"
          @click="drawer = true"
        />

        <v-spacer />
      </v-app-bar>
    </v-card>

    <v-navigation-drawer
      v-model="drawer"
      absolute
      temporary
    >
      <v-list
        nav
        dense
      >
        <v-list-item-group
          active-class="deep-blue--text text--accent-4"
        >
          <v-card
            elevation="0"
            class="d-flex justify-center"
          >
            <v-img
              alt="Blue Robotics Logo"
              class="shrink mr-2"
              contain
              src="./assets/logo.svg"
              width="60"
            />
          </v-card>

          <v-card
            elevation="0"
            height="30"
            class="pa-4"
          >
            <v-divider />
          </v-card>

          <v-list-item to="/">
            <v-list-item-icon>
              <v-icon>mdi-home</v-icon>
            </v-list-item-icon>
            <v-list-item-title>Main</v-list-item-title>
          </v-list-item>
        </v-list-item-group>
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <router-view />
    </v-main>
    <services-scanner />
  </v-app>
</template>

<script lang="ts">
import Vue from 'vue'
import ServicesScanner from './components/scanner/servicesScanner.vue'

export default Vue.extend({
  name: 'App',

  components: {
    'services-scanner': ServicesScanner,
  },

  data: () => ({
    drawer: false,
  }),
})
</script>
