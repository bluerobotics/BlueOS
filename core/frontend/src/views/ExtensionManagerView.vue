<template>
  <v-container fluid>
    <!-- Progress Pull -->
    <!-- Extension Detail Modal -->
    <!-- Settings  Modal-->
    <!-- Log Modal -->
    <v-toolbar>
      <v-spacer />
      <v-tabs
        v-model="tab"
      >
        <v-tab class="px-5">
          <v-icon class="mr-5">
            mdi-package-variant
          </v-icon>
          Inventory
        </v-tab>
        <v-tab class="px-5">
          <v-icon class="mr-5">
            mdi-bookshelf
          </v-icon>
          Installed
        </v-tab>
      </v-tabs>
      <v-spacer />
      <v-text-field
        v-model.trim="searching_query"
        dense
        rounded
        filled
        clearable
        placeholder="Search Extensions"
        prepend-inner-icon="mdi-magnify"
        class="pt-6 mt-6 pb-6 shrink expanding-search"
        :class="{ closed: !is_searching && !searching_query }"
        @focus="is_searching = true"
        @blur="is_searching = false"
      />
      <v-btn
        v-tooltip="'Settings'"
        icon
        color="gray"
        hide-details="auto"
      >
        <v-icon>mdi-cog</v-icon>
      </v-btn>

      <template #extension>
      </template>
    </v-toolbar>
    <!-- Public Store Ext -->
    <!-- Inventory Ext -->
    <!-- Installed Ext -->
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'ExtensionManagerView',
  components: {
  },
  data() {
    return {
      tab: 0,
      searching_query: '',
      is_searching: false,
    }
  },
  computed: {
  },
  mounted() {
    this.fetchManifest()
  },
  destroyed() {
    // clearInterval(this.metrics_interval)
  },
  methods: {
    async fetchManifest(): Promise<void> {
      // Pass
    },
  },
})
</script>

<style>
.search-container {
  flex: 1 1 auto;
  width: 50% !important;
}

.v-input.expanding-search {
  transition: max-width 0.2s;
}

.v-input.expanding-search .v-input__slot {
  cursor: pointer;
}

.v-input.expanding-search.closed {
  max-width: 70px;
}
</style>
