<template>
  <v-dialog
    v-model="show_dialog"
    width="80%"
  >
    {{ value?.name }}
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { ExtensionData } from '@/types/kraken'

export default Vue.extend({
  name: 'ExtensionDetailsModal',
  props: {
    value: {
      type: Object as PropType<ExtensionData>,
      required: false,
      default: undefined,
    },
  },
  data() {
    return {
      show_dialog: false,
    }
  },
  watch: {
    value(val: ExtensionData | undefined) {
      if (val !== undefined) {
        this.show_dialog = true
      }
    },
    show_dialog(val: boolean) {
      if (!val) {
        this.$emit('input', undefined)
      }
    },
  },
})
</script>
<style>
div.readme {
  line-height: 200%;
}
div.readme p {
  margin-top: 10px;
  margin-left: 20px;
}
div.readme pre {
  margin-left: 20px;
}
div.readme h1 {
  margin-bottom: 20px;
}

div.readme h2 {
  margin-bottom: 10px;
  margin-left: 10px;
}

div.readme h3 {
  margin-bottom: 10px;
  margin-left: 20px;
}

div.readme ul {
  margin-left: 20px;
}
</style>
