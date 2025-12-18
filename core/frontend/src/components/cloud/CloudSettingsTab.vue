<template>
  <v-container class="text-center fill-height d-flex flex-column justify-center align-center mt-5">
    <v-icon
      :color="isTokenSet ? 'green' : 'yellow'"
      size="70"
    >
      {{ isTokenSet ? 'mdi-weather-cloudy' : 'mdi-wrench' }}
    </v-icon>
    <v-card-title>
      {{ isTokenSet ? 'Setup is complete!' : 'Lets connect your vehicle!' }}
    </v-card-title>
    <v-btn
      color="primary"
      elevation="3"
      class="mt-4"
      :href="isTokenSet ? blueosCloudUrl : blueosCloudVehiclesUrl"
      target="_blank"
      rel="noopener noreferrer"
      @click="() => {}"
    >
      Go to BlueOS Cloud
    </v-btn>
    <v-container
      class="d-flex align-center py-0 my-0"
      style="height: 90px; width: auto;"
    >
      <v-card-subtitle
        v-if="!settingToken"
        class="token-link-text mt-2 pt-1 pb-1"
        @click="$emit('toggle-token-input', true)"
      >
        Click here if you {{ isTokenSet ? 'want to change your token' : 'already have a token' }}
      </v-card-subtitle>
      <v-slide-x-reverse-transition>
        <v-text-field
          v-if="settingToken"
          :value="token"
          label="Token"
          type="text"
          variant="outlined"
          @input="$emit('update:token', $event)"
        >
          <template #append>
            <v-btn
              icon
              @click="$emit('submit-token')"
            >
              <v-icon
                color="primary"
                size="30"
              >
                mdi-check-circle-outline
              </v-icon>
            </v-btn>
          </template>
        </v-text-field>
      </v-slide-x-reverse-transition>
    </v-container>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'CloudSettingsTab',
  props: {
    isTokenSet: {
      type: Boolean,
      required: true,
    },
    settingToken: {
      type: Boolean,
      required: true,
    },
    token: {
      type: String,
      required: true,
    },
    blueosCloudUrl: {
      type: String,
      required: true,
    },
    blueosCloudVehiclesUrl: {
      type: String,
      required: true,
    },
  },
})
</script>

<style scoped>
.token-link-text {
  cursor: pointer;
  text-decoration: underline;
}
</style>
