<template>
  <v-card
    elevation="1"
    width="250"
  >
    <v-list>
      <v-list-item>
        <v-switch
          :input-value="showOld"
          color="primary"
          @change="emitShowOldChange"
        />
        <div>Show old messages</div>
      </v-list-item>
      <v-list-item>
        <v-switch
          :input-value="groupByService"
          color="primary"
          @change="emitGroupByServiceChange"
        />
        <div>Group by service</div>
      </v-list-item>
    </v-list>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'NotificationsConfigMenu',
  props: {
    groupByService: {
      type: Boolean,
    },
    showOld: {
      type: Boolean,
    },
  },
  methods: {
    emitGroupByServiceChange(value: boolean): void {
      this.$emit('update:group-by-service', value)
    },
    emitShowOldChange(value: boolean): void {
      this.$emit('update:show-old', value)
    },
  },
})
</script>
