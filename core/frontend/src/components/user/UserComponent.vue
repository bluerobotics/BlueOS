<template>
  <v-card>
    <v-card-title><p>This is an http-loaded component!</p></v-card-title>
    <v-card-text>
      Does it have access to the stores?
      Temp: {{ cpu_temperature }}
      <v-card-text />
    </v-card-text>
  </v-card>
</template>

<script>
import { defineComponent } from '@vue/composition-api'

import system_information from '@/store/system-information'

// 1 - Create a 'server' folder
// 2 - comment the line in App.vue
// 3 - set the correct url in MainView.vue
// 4 - run this command to build the code:
// npx vue-cli-service build --target lib --formats umd-min --no-clean --dest server/UserComponent --name "UserComponent" src/components/user/UserComponent.vue
// then run python3 http.server in the 'server' folder, and run yarn serve as usual

export default defineComponent({
  name: 'UserComponent',
  computed: {
    cpu_temperature() {
      const temperature_sensors = system_information.system?.temperature
      const main_sensor = temperature_sensors?.find((sensor) => sensor.name === 'CPU')
      return main_sensor ? main_sensor.temperature.toFixed(1) : 'Loading..'
    },
  },
})
</script>
