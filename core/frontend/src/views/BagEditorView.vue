<template>
  <json-editor
    v-model="json"
    style="width:100%; height:100%"
    @save="apply"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import JsonEditor from '@/components/common/JsonEditor.vue'
import bag from '@/store/bag'

export default Vue.extend({
  name: 'BagEditorView',
  components: {
    JsonEditor,
  },
  data() {
    return {
      json: {} as any,
    }
  },
  async mounted() {
    this.json = await bag.getData('*')
  },
  methods: {
    apply(json: any) {
      bag.overwrite(json)
      this.json = json
    },
  },
})
</script>
