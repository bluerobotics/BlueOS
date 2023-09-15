import '@mdi/font/css/materialdesignicons.css'

import simple_icons from 'simple-icons'
import Vue from 'vue'
import Vuetify from 'vuetify/lib/framework'

import * as BR_COLORS from '@/style/colors/blue_robotics'
import * as DEFAULT_COLORS from '@/style/colors/default'

Vue.use(Vuetify)

const vuetify = new Vuetify({
  icons: {
    iconfont: 'mdi',
  },
  theme: {
    options: { customProperties: true },
    themes: {
      light: {
        // Default colors used by BlueOS
        primary: DEFAULT_COLORS.PRIMARY,
        secondary: DEFAULT_COLORS.SECONDARY,
        accent: DEFAULT_COLORS.ACCENT,
        success: DEFAULT_COLORS.SUCCESS,
        error: DEFAULT_COLORS.ERROR,
        info: DEFAULT_COLORS.INFO,
        warning: DEFAULT_COLORS.WARNING,
        critical: DEFAULT_COLORS.CRITICAL,

        // Colors from Blue Robotics color palette
        br_blue: BR_COLORS.BR_BLUE,
        mariner_blue: BR_COLORS.MARINER_BLUE,
        blue_whale: BR_COLORS.BLUE_WHALE,
        tether_yellow: BR_COLORS.TETHER_YELLOW,
        tuna: BR_COLORS.TUNA,
        oyster: BR_COLORS.OYSTER,
      },
      dark: {
        // Default colors used by BlueOS
        primary: DEFAULT_COLORS.PRIMARY,
        secondary: DEFAULT_COLORS.SECONDARY,
        accent: DEFAULT_COLORS.ACCENT,
        success: DEFAULT_COLORS.SUCCESS,
        error: DEFAULT_COLORS.ERROR,
        info: DEFAULT_COLORS.INFO,
        warning: DEFAULT_COLORS.WARNING,
        critical: DEFAULT_COLORS.CRITICAL,

        // Colors from Blue Robotics color palette
        br_blue: BR_COLORS.BR_BLUE,
        mariner_blue: BR_COLORS.MARINER_BLUE,
        blue_whale: BR_COLORS.BLUE_WHALE,
        tether_yellow: BR_COLORS.TETHER_YELLOW,
        tuna: BR_COLORS.TUNA,
        oyster: BR_COLORS.OYSTER,
      },
    },
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
