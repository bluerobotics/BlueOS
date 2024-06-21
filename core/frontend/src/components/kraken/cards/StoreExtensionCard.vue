<template>
  <v-card outlined width="300" height="auto" elevation="2" class="store-extension-card">
    <v-card-title class="d-flex justify-space-between align-center py-1 px-3">
      <span class="date-time">MON 12:00 AM</span>
    </v-card-title>

    <v-img contain :src="extension.extension_logo" height="150px" class="mx-3 mt-2" />

    <v-card-subtitle class="px-3 py-2">
      <div class="event-title">NEW SEASON</div>
      <div class="event-description">Join the Fireworks Festival</div>
      <div class="event-details">Attend a party full of prizes in Candy Crush Saga.</div>
    </v-card-subtitle>

    <v-card-actions class="px-3 py-2 d-flex justify-space-between align-center">
      <v-avatar size="32">
        <img src="https://example.com/your-icon-url.png" alt="Candy Crush Saga">
      </v-avatar>
      <div class="game-info">
        <div class="game-name">CANDY CRUSH SAGA</div>
        <div class="event-name">Fireworks Festival</div>
      </div>
      <v-btn small color="primary">GET</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { ExtensionData } from '@/types/kraken'

export default Vue.extend({
  name: 'StoreExtensionCard',
  props: {
    extension: {
      type: Object as PropType<ExtensionData>,
      required: true,
    },
  },
  computed: {
    isCompatible(): boolean {
      return this.extension.is_compatible ?? true
    },
    compatibleArchs(): string[] {
      const archs = [
        ...new Set(
          Object.values(this.extension.versions)
            .flatMap((version) => version.images)
            .flatMap((image) => image.platform.architecture),
        ),
      ]

      return archs
    },
  },
})
</script>

<style scoped>
.store-extension-card {
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  transition: transform 0.3s;
  cursor: pointer;
}

.store-extension-card:hover {
  transform: translateY(-5px);
}

.date-time {
  background-color: #4a90e2;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.event-title {
  font-weight: bold;
  color: #4a90e2;
  font-size: 14px;
}

.event-description {
  font-weight: bold;
  font-size: 18px;
}

.event-details {
  color: gray;
  font-size: 14px;
}

.game-info {
  flex-grow: 1;
  margin-left: 8px;
}

.game-name {
  font-weight: bold;
  font-size: 14px;
}

.event-name {
  color: gray;
  font-size: 12px;
}

.v-card-actions {
  margin-top: auto;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.v-img {
  border-radius: 8px;
}

.v-avatar img {
  object-fit: cover;
}

.disabled-card {
  opacity: 0.5;
  position: relative;
}
.disabled-card::before {
  opacity: 1;
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    135deg,
    rgba(255, 255, 255, 0),
    rgba(255, 255, 255, 0) 15px,
    rgba(100, 85, 85, 0.4) 10px,
    rgba(100, 85, 85, 0.4) 16px
  );
  pointer-events: none;
}
</style>
