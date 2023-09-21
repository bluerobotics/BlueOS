<template>
  <v-container class="d-flex flex-column align-center justify-space-between">
    <v-img
      :aspect-ratio="1 / 1"
      class="lds-dual-ring"
      :width="size"
      :src="require('@/assets/img/blue-robotics-logo.svg')"
    />
    <span class="text-subtitle-2">{{ subtitle }}</span>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'SpinningLogo',
  props: {
    size: {
      type: String,
      required: true,
    },
    subtitle: {
      type: String,
      required: false,
      default: '',
    },
  },
})
</script>

<style>
  .lds-dual-ring {
    display: block;
    margin: 5% auto;
    animation-name: rotation360;
    animation-duration: 2s;
    animation-iteration-count: infinite;
  }
  @keyframes rotation360 {
    0% {
        transform: rotate(0deg);
    }
    100% {
        transform: rotate(360deg);
    }
  }
</style>
