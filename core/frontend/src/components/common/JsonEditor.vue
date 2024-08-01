<template>
  <div class="d-flex flex-column">
    <div
      v-if="!is_read_only"
      class="editor d-flex"
    >
      <v-btn
        v-tooltip="mode_tooltip"
        class="editor-control"
        icon
        color="white"
        @click="toggleMode"
      >
        <v-icon> {{ mode_icon }} </v-icon>
      </v-btn>

      <v-divider />

      <slot name="controls" />
      <v-btn
        v-tooltip="save_tooltip"
        class="editor-control"
        icon
        color="white"
        @click="save"
      >
        <v-icon> {{ save_icon }} </v-icon>
      </v-btn>
    </div>
    <div
      ref="jsonEditor"
      class="align-self-stretch"
      style="flex-grow: 1;"
    />
  </div>
</template>

<script>
import 'jsoneditor/dist/jsoneditor.min.css'

import JSONEditor from 'jsoneditor'

export default {
  name: 'JsonEditor',
  props: {
    value: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      editor: null,
      code_mode: true,
      edited_code: '',
    }
  },
  computed: {
    mode_icon() {
      return this.code_mode ? 'mdi-file-tree' : 'mdi-text-long'
    },
    mode_tooltip() {
      return this.code_mode ? 'Tree Mode' : 'Code Mode'
    },
    is_different() {
      return JSON.stringify(this.edited_code) !== JSON.stringify(this.value)
    },
    save_icon() {
      return this.is_different ? 'mdi-content-save-edit-outline' : 'mdi-content-save-check-outline'
    },
    save_tooltip() {
      return this.is_different ? 'Apply changes' : 'Saved'
    },
    is_read_only() {
      return this.readOnly
    },
    editor_code_mode() {
      if (this.readOnly) {
        return 'view'
      }

      return this.code_mode ? 'code' : 'tree'
    },
  },
  watch: {
    value(json) {
      if (JSON.stringify(json) !== JSON.stringify(this.editor.get())) {
        this.edited_code = json
        this.editor.set(json)
      }
    },
    readOnly() {
      this.editor.setMode(this.read ? 'view' : this.editor_code_mode)
    },
  },
  mounted() {
    const options = {
      onChange: () => {
        try {
          this.edited_code = this.editor.get()
        } catch { /* Json not valid */ }
      },
      mode: this.editor_code_mode,
    }
    this.editor = new JSONEditor(this.$refs.jsonEditor, options, this.value)
    this.edited_code = this.value
  },
  beforeDestroy() {
    this.editor.destroy()
  },
  methods: {
    save() {
      this.$emit('save', this.edited_code)
    },
    toggleMode() {
      this.code_mode = !this.code_mode
      this.editor.setMode(this.code_mode ? 'code' : 'tree')
    },
  },
}
</script>

<style scoped>
.editor-control {
  margin: 0;
  opacity: 0.7;
}

.editor {
  background-color: #3883fa;
  border: thin solid #3883fa;
  box-sizing: border-box;
  position: relative;
  padding: 0;
  line-height: 100%;
}
</style>
