<template>
  <v-container>
    <v-row
      class="mb-6 mt-6"
      justify="center"
      no-gutters
    >
      <v-alert
        v-if="!current_network"
        border="top"
        colored-border
        type="info"
        elevation="2"
        dismissible
      >
        <h3>Welcome to BlueOS!</h3>
        Before you start, we highly recommend <a
          href="https://docs.bluerobotics.com/ardusub-zola/software/onboard/BlueOS-1.0/getting-started/#connect-wifi"
          target="_blank"
        >
          connecting to the internet
        </a>
        and performing a <a
          href="https://docs.bluerobotics.com/ardusub-zola/software/onboard/BlueOS-1.0/getting-started/#select-version"
          target="_blank"
        >
          system update to the latest available BlueOS version
        </a>
        .
      </v-alert>
      <self-health-test />
    </v-row>
    <div class="grid-holder">
      <div class="grid-holder-container">
        <div
          v-for="({
            icon, title, text, route, advanced,
          }, i) in apps"
          :key="i"
        >
          <v-card
            class="mb-3 px-3 rounded-xl app-card"
            :href="route"
          >
            <v-theme-provider dark>
              <v-row
                class="py-3 px-3 d-flex justify-space-between flex-nowrap"
              >
                <v-card-title
                  class="text-subtitle-2 font-weight-bold"
                  v-text="title"
                />
                <div>
                  <v-avatar
                    color="primary"
                    size="50"
                  >
                    <v-icon
                      large
                      v-text="icon"
                    />
                  </v-avatar>
                </div>
              </v-row>
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
            <v-card-text
              class="subtitle-1 text-justify-start text-clamp pt-0 pb-0"
              v-text="text"
            />
          </v-card>
        </div>
      </div>
    </div>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import SelfHealthTest from '@/components/health/SelfHealthTest.vue'
import settings from '@/libs/settings'
import wifi from '@/store/wifi'
import { Network } from '@/types/wifi'

import menus, { menuItem } from '../menus'

export default Vue.extend({
  name: 'MainView',
  components: {
    SelfHealthTest,
  },
  data: () => ({
    menus,
    settings,
  }),
  computed: {
    apps() {
      const items: menuItem[] = []
      for (const item of this.menus) {
        if (item?.route && (!item.advanced || this.settings.is_pirate_mode)) {
          items.push(item)
          continue
        }

        for (const subitem of item?.submenus || []) {
          if (!subitem.advanced || this.settings.is_pirate_mode) {
            items.push(subitem)
          }
        }
      }
      return items
    },
    current_network(): Network | null {
      return wifi.current_network
    },
  },
})
</script>

<style scoped>

.rounded-card {
  border-radius:50px;
}

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

.text-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.grid-holder {
  padding: 10px;
}

.grid-holder-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
  justify-content: center;
}

.app-card {
  width: auto;
  min-width: 300px;
  height: 200px;
  transition: transform 0.3s;
}

.app-card:hover {
  transform: translateY(-5px);
}

@media (max-width: 677px) {
  .grid-holder-container {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }
  .app-card {
    width: 100%;
  }
}
</style>
