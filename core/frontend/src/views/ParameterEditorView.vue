<template>
  <v-container>
    <parameter-editor />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import ParameterEditor from '@/components/parameter-editor/ParameterEditor.vue'

export default Vue.extend({
  name: 'ParameterEditorView',
  components: {
    ParameterEditor,
  },
})
</script>
