<template>
  <v-container fluid>
    <v-tabs
      v-model="page_selected"
      centered
      show-arrows
    >
      <v-tabs-slider />
      <v-tab
        v-for="page in filtered_pages"
        :key="`title-${page.title}`"
      >
        {{ page.title }}
      </v-tab>
    </v-tabs>
    <v-tabs-items v-model="page_selected">
      <v-tab-item
        v-for="page in filtered_pages"
        :key="`item-${page.title}`"
      >
        <component :is="page.component" />
      </v-tab-item>
    </v-tabs-items>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot from '@/store/autopilot_manager'

import LightsConfigration from './configuration/lights.vue'
import ParamSets from './overview/ParamSets.vue'

export interface Item {
  title: string,
  icon: string,
  component: unknown,
  filter?: () => boolean,
}

export default Vue.extend({
  name: 'Configure',
  components: {
    ParamSets,
    LightsConfigration,
  },
  data() {
    return {
      page_selected: null as string | null,
      pages: [
        { title: 'Parameters', component: ParamSets },
        { title: 'Accelerometer', component: undefined },
        { title: 'Compass', component: undefined },
        { title: 'Baro', component: undefined },
        { title: 'Gripper', component: undefined },
        { title: 'Lights', component: LightsConfigration, filter: () => autopilot.vehicle_type === 'Submarine' },
        { title: 'Camera Mount', component: undefined },
      ] as Item[],
    }
  },
  computed: {
    filtered_pages() {
      // eslint-disable-next-line no-extra-parens
      return this.pages.filter((page) => (page.filter ? page.filter() : true))
    },
  },
})
</script>
