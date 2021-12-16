import vuetify from '@/plugins/vuetify'
import settingsStore from '@/store/settings'

class Settings {
  // eslint-disable-next-line
  get is_dark_theme(): boolean {
    vuetify.framework.theme.dark = settingsStore.is_dark_theme
    return settingsStore.is_dark_theme
  }

  // eslint-disable-next-line
  set is_dark_theme(value: boolean) {
    settingsStore.setDarkTheme(value)
  }
}

const settings = new Settings()

export default settings
