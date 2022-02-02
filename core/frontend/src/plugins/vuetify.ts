import '@mdi/font/css/materialdesignicons.css'

import simple_icons from 'simple-icons'
import Vue from 'vue'
import Vuetify from 'vuetify/lib/framework'

Vue.use(Vuetify)

const vuetify = new Vuetify({
  icons: {
    iconfont: 'mdi',
  },
})

// Add simple-icons on vuetify
// Use `$si-${name}` to access it
// E.g: <v-icon> $si-discourse </v-icon>
const icons = Object.entries(simple_icons).map(([key]) => ({
  name: key,
  simple_icon: simple_icons.Get(key),
}))

for (const icon of icons) {
  vuetify.framework.icons.values[`si-${icon.simple_icon.slug}`] = `${icon.simple_icon.path}`
}

export default vuetify
