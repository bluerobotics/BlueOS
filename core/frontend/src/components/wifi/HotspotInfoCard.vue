<template>
  <v-card-text class="text-center pa-6">
    <div
      v-if="loading"
      class="d-flex flex-column align-center justify-center py-8"
    >
      <v-progress-circular
        indeterminate
        color="primary"
        size="64"
        class="mb-4"
      />
      <div class="text-body-1 grey--text">
        Updating hotspot settings...
      </div>
    </div>

    <template v-else>
      <div class="hotspot-icon-container mb-4">
        <v-icon
          size="80"
          color="primary"
          class="hotspot-icon"
        >
          mdi-access-point
        </v-icon>
        <div class="hotspot-pulse" />
      </div>

      <div class="text-h5 font-weight-bold primary--text mb-1">
        Hotspot Active
      </div>

      <v-card
        v-if="qrCodeImg"
        class="mx-auto mb-4 pa-3"
        max-width="220"
        elevation="2"
        rounded="lg"
      >
        <img
          :src="qrCodeImg"
          alt="WiFi QR Code"
          class="qr-code-img"
        >
        <div class="text-caption grey--text mt-2">
          Scan to connect
        </div>
      </v-card>

      <v-card
        class="mx-auto credentials-card"
        max-width="300"
        outlined
        rounded="lg"
      >
        <v-list
          dense
          class="py-0"
        >
          <v-list-item v-if="ssid">
            <v-list-item-icon class="mr-3">
              <v-icon color="primary">
                mdi-wifi
              </v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-subtitle>Network Name</v-list-item-subtitle>
              <v-list-item-title class="font-weight-medium">
                {{ ssid }}
              </v-list-item-title>
            </v-list-item-content>
          </v-list-item>
          <v-divider />
          <v-list-item v-if="password">
            <v-list-item-icon class="mr-3">
              <v-icon color="primary">
                mdi-key
              </v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-subtitle>Password</v-list-item-subtitle>
              <v-list-item-title class="font-weight-medium">
                {{ password }}
              </v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list>
      </v-card>
    </template>
  </v-card-text>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'HotspotInfoCard',
  props: {
    ssid: {
      type: String,
      default: null,
    },
    password: {
      type: String,
      default: null,
    },
    qrCodeImg: {
      type: String,
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
})
</script>

<style scoped>
.hotspot-icon-container {
  position: relative;
  display: inline-block;
}

.hotspot-icon {
  position: relative;
  z-index: 1;
}

.hotspot-pulse {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: var(--v-primary-base);
  opacity: 0.2;
  animation: pulse 2s ease-out infinite;
}

@keyframes pulse {
  0% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 0.3;
  }
  100% {
    transform: translate(-50%, -50%) scale(1.5);
    opacity: 0;
  }
}

.qr-code-img {
  width: 180px;
  height: 180px;
  display: block;
  margin: 0 auto;
}

.credentials-card {
  background: rgba(var(--v-primary-base), 0.02);
}
</style>
