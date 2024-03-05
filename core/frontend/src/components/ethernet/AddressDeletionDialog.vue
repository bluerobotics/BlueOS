<template>
  <v-dialog
    width="350"
    :value="show"
    @input="resolve"
  >
    <v-card>
      <v-card-title>{{ title }}</v-card-title>

      <v-card-subtitle class="text-center mb-3 mt-3">
        {{ message }}
      </v-card-subtitle>

      <v-card-text class="d-flex flex-row justify-space-around">
        <v-btn
          color="grey"
          class="ma-2 elevation-2"
          text
          @click="resolve(false)"
        >
          Abort
        </v-btn>
        <v-btn
          color="primary"
          class="ma-2 elevation-2"
          text
          @click="resolve(true)"
        >
          Confirm
        </v-btn>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'AddressDeletionDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    dialogType: {
      type: String,
      default: '',
      validator: (value: string) => ['', 'last-ip-address', 'ip-being-used'].includes(value),
    },
  },
  data() {
    return {
      resolveCallback: undefined as ((state: boolean) => void) | undefined,
    }
  },
  computed: {
    title() {
      if (this.dialogType === 'last-ip-address') {
        return 'Last IP address'
      }
      if (this.dialogType === 'ip-being-used') {
        return 'IP address in use'
      }

      return 'IP Deletion'
    },
    message() {
      if (this.dialogType === 'last-ip-address') {
        return 'This is the last IP address on this interface.'
          + ' Deleting it could prevent you from accessing your vehicle. Are you sure you want to proceed?'
      }
      if (this.dialogType === 'ip-being-used') {
        return 'The IP address is currently being used to access BlueOS.'
          + ' Deleting it could prevent you from accessing your vehicle. Are you sure you want to proceed?'
      }

      return 'Are you sure you want to delete this IP address?'
    },
  },
  methods: {
    resolve(state: boolean) {
      this.resolveCallback?.(state)
      this.$emit('change', false)
    },
  },
})
</script>
