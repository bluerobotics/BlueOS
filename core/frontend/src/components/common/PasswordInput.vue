<template>
  <v-text-field
    :value="value"
    :append-icon="password_show_icon"
    :type="input_field_type"
    label="Password"
    hide-details="auto"
    class="pa-2"
    @input="emitInput"
    @keyup.enter="emitSubmit"
    @click:append="togglePasswordShow"
    @submit.prevent=""
  />
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'PasswordInput',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  data() {
    return {
      show_password: false,
    }
  },
  computed: {
    password_show_icon(): string {
      return this.show_password ? 'mdi-eye' : 'mdi-eye-off'
    },
    input_field_type(): string {
      return this.show_password ? 'text' : 'password'
    },
  },
  methods: {
    togglePasswordShow() {
      this.show_password = !this.show_password
    },
    emitInput(value: string) {
      this.$emit('input', value)
    },
    emitSubmit() {
      this.$emit('submit')
    },
  },
})
</script>
