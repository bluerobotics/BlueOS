<template>
  <div class="ma-4 d-flex justify-center">
    <!-- this is theoretically not safe, but we have a command that gives users root access, so... -->
    <!-- eslint-disable vue/no-v-html -->
    <i :class="`${svg_outside_style} svg-icon`" v-html="image" />
  </div>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import settings from '@/store/settings'

export default Vue.extend({
  name: 'ThemedSVG',
  props: {
    src: {
      type: String,
      required: true,
    },

  },
  data() {
    return {
      image: '',
    }
  },
  computed: {
    svg_outside_style(): string {
      return `mr-0 ${settings.is_dark_theme ? 'svg-outline-dark' : 'svg-outline-light'}`
    },
  },
  watch: {
    src() {
      axios.get(this.src).then((response) => {
        this.image = response.data
      }).catch((error) => {
        console.error(error)
      })
    },
  },
  mounted() {
    axios.get(this.src).then((response) => {
      this.image = response.data
    }).catch((error) => {
      console.error(error)
    })
  },
})

</script>
<style>
i.svg-icon svg {
  height: 100% !important;
  min-width: 180px;
}

i.svg-outline-dark path {
  fill: #D1EAF1;
}

i.svg-outline-light path {
  fill: #002F45;
}

i.svg-outline-dark text {
  fill: #D1EAF1 !important;
}

i.svg-outline-light text {
  fill: #002F45 !important;
}
</style>
