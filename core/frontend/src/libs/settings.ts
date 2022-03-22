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

  // eslint-disable-next-line
  get is_pirate_mode(): boolean {
    return settingsStore.is_pirate_mode
  }

  // eslint-disable-next-line
  set is_pirate_mode(value: boolean) {
    settingsStore.setPirateMode(value)
  }

  // eslint-disable-next-line
  get last_version_update_notification_time(): Date {
    const time = settingsStore.last_version_update_notification_time
    return time ? new Date(time) : new Date(0)
  }

  // eslint-disable-next-line
  updateVersionUpdateNotificationTime() {
    settingsStore.updateVersionUpdateNotificationTime()
  }
}

const settings = new Settings()

export default settings
