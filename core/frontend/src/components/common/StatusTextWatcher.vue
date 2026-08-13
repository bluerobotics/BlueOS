<template>
  <div>
    <div
      v-for="(entry, index) in messages"
      :key="index"
      :class="entry.color"
    >
      {{ entry.text }}
    </div>
  </div>
</template>

<script lang="ts">
import mavlink2rest from '@/libs/MAVLink2Rest'
import Listener from '@/libs/MAVLink2Rest/Listener'

type StatusLine = {
  text: string
  color: string
}

export default {
  name: 'StatusTextWatcher',
  props: {
    filter: {
      type: RegExp,
      default: /.*/,
    },
  },
  data() {
    return {
      messages: [] as StatusLine[],
      listener: undefined as undefined | Listener,
    }
  },
  mounted() {
    this.listener = mavlink2rest.startListening('STATUSTEXT').setCallback((receivedMessage) => {
      const text = receivedMessage.message.text.join('')
      const last = this.messages[this.messages.length - 1]
      if (last?.text === text) {
        return
      }
      if (new RegExp(this.filter).test(text)) {
        this.$emit('message', text)
        this.messages.push({ text, color: this.colorFrom(text) })
      }
    }).setFrequency(0)
  },
  beforeDestroy() {
    this.listener?.discard()
  },
  methods: {
    colorFrom(text: string): string {
      const lower = text.toLowerCase()
      if (lower.includes('failed')) {
        return 'error--text'
      }
      if (lower.includes('bad thrust')) {
        return 'warning--text'
      }
      if (lower.includes('is ok') || lower.includes('reversed') || lower.includes('complete')) {
        return 'success--text'
      }
      return ''
    },
  },
}
</script>
