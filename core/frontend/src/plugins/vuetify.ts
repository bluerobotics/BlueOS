import '@mdi/font/css/materialdesignicons.css'

import { siDiscourse } from 'simple-icons';
import Vue from 'vue'
import Vuetify from 'vuetify/lib/framework'

import * as BR_COLORS from '@/style/colors/blue_robotics'
import * as DEFAULT_COLORS from '@/style/colors/default'

Vue.use(Vuetify)

const baseTheme = {
  // Default colors used by BlueOS
  primary: DEFAULT_COLORS.PRIMARY,
  secondary: DEFAULT_COLORS.SECONDARY,
  accent: DEFAULT_COLORS.ACCENT,
  success: DEFAULT_COLORS.SUCCESS,
  error: DEFAULT_COLORS.ERROR,
  info: DEFAULT_COLORS.INFO,
  warning: DEFAULT_COLORS.WARNING,
  critical: DEFAULT_COLORS.CRITICAL,

  // Colors for explanatory diagrams
  water: BR_COLORS.BR_BLUE,
  detail: BR_COLORS.BLUE_WHALE,
  positive: BR_COLORS.KELP_GREEN,
  neutral: BR_COLORS.GARIBALDI_ORANGE,
  negative: BR_COLORS.AXOLOTL_PINK,
  attention: BR_COLORS.TETHER_YELLOW,

  // Colors from Blue Robotics color palette
  br_blue: BR_COLORS.BR_BLUE,
  mariner_blue: BR_COLORS.MARINER_BLUE,
  blue_whale: BR_COLORS.BLUE_WHALE,
  tether_yellow: BR_COLORS.TETHER_YELLOW,
  tuna: BR_COLORS.TUNA,
  oyster: BR_COLORS.OYSTER,
}

const vuetify = new Vuetify({
  icons: {
    iconfont: 'mdi',
  },
  theme: {
    options: { customProperties: true },
    themes: {
      light: {
        // Colors common to both themes
        ...baseTheme,
        
        // BlueOS light theme defaults
        sheet_bg: DEFAULT_COLORS.SHEET_LIGHT_BG,
        sheet_bg_complement: DEFAULT_COLORS.SHEET_DARK_BG,

        // Diagram light theme colors
        outline: BR_COLORS.BLUE_WHALE,
      },
      dark: {
        // Colors common to both themes
        ...baseTheme,
        
        // BlueOS dark theme defaults
        sheet_bg: DEFAULT_COLORS.SHEET_DARK_BG,
        sheet_bg_complement: DEFAULT_COLORS.SHEET_LIGHT_BG,
        
        // Diagram dark theme colors
        outline: BR_COLORS.SKY_BLUE,
      },
    },
  },
})

// Add any other icons here
// this usage is required for tree-shaking to work,
// otherwise all icons will be included in the bundle
const icons = [
  siDiscourse
].map((icon) => {
  return {
    'name': icon.title,
    'slug': icon.slug,
    'path': icon.path
  }
})

for (const icon of icons) {
  vuetify.framework.icons.values[`si-${icon.slug}`] = `${icon.path}`
}

export default vuetify
