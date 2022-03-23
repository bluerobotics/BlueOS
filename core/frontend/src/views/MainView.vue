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

    <v-row>
      <v-col
        v-for="({ icon, title, text, route, advanced}, i) in apps"
        :key="i"
        cols="12"
        md="3"
        class="mt-10"
      >
        <v-card
          class="py-4 px-4"
          style="min-height: 100%"
          :href="route"
        >
          <v-theme-provider dark>
            <div>
              <v-avatar
                color="primary"
                size="88"
              >
                <v-icon
                  large
                  v-text="icon"
                />
              </v-avatar>
            </div>
          </v-theme-provider>
          <v-theme-provider dark>
            <div
              v-if="advanced"
              v-tooltip="'This is an advanced feature'"
              class="pirate-marker"
            >
              <v-avatar
                color="error"
                size="35"
              >
                <v-icon
                  v-text="'mdi-skull-crossbones'"
                />
              </v-avatar>
            </div>
          </v-theme-provider>

          <v-card-title
            class="justify-center font-weight-black text-uppercase mt-0"
            v-text="title"
          />

          <v-card-text
            class="subtitle-1 text-justify"
            v-text="text"
          />
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'

import menus, { menuItem } from '../menus'

export default Vue.extend({
  name: 'Main',
  data: () => ({
    menus,
    settings,
  }),
  computed: {
    apps() {
      const items: menuItem[] = []
      for (const item of this.menus) {
        for (const subitem of item.submenus || []) {
          if (!subitem.advanced || this.settings.is_pirate_mode) {
            items.push(subitem)
          }
        }
      }
      return items
    },
  },
})
</script>

<style>

div.pirate-marker {
  position: absolute;
  width: 35px;
  right: 0;
  top: 0px;
  opacity: 0.7;
}

div.pirate-marker.v-icon {
    font-size: 10px;
}

</style>
