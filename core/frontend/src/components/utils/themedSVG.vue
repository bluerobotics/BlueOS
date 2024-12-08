<template>
  <div class="ma-4 d-flex justify-center">
    <!-- this is theoretically not safe, but we have a command that gives users root access, so... -->
    <!-- eslint-disable vue/no-v-html -->
    <i class="svg-icon" v-html="image" />
  </div>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

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
</style>
