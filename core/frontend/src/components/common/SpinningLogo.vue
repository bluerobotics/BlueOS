<template>
  <v-img
    :aspect-ratio="1/1"
    class="lds-dual-ring"
    :width="size"
    src="../../assets/img/logo.svg"
  />
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
