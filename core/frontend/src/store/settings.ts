import Vue from 'vue'
import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import beacon from '@/store/beacon'
import { castString } from '@/utils/helper_functions'

@Module({
  dynamic: true,
  store,
  name: 'settings',
})

class SettingsStore extends VuexModule {
  // Variable for version control of the settings structure
  settings_version = 1

  is_dark_theme: boolean = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches

  is_pirate_mode = false

  is_dev_mode_enabled = false

  last_version_update_notification_time = 0 // Start in 1970: https://www.youtube.com/watch?v=wwcKs5K1oWg

  tour_version = 0

  user_top_widgets = [] as string[]

  @Mutation
  setDarkTheme(value: boolean): void {
    this.is_dark_theme = value
    SettingsStore.save()
  }

  @Mutation
  setPirateMode(value: boolean): void {
    this.is_pirate_mode = value
    if (!value) {
      this.is_dev_mode_enabled = false
    }
    SettingsStore.save()
  }

  @Mutation
  setDevMode(value: boolean): void {
    this.is_dev_mode_enabled = value && this.is_pirate_mode
    SettingsStore.save()
  }

  @Mutation
  updateVersionUpdateNotificationTime(): void {
    this.last_version_update_notification_time = new Date().getTime()
    SettingsStore.save()
  }

  @Mutation
  setTourVersion(value: number): void {
    this.tour_version = value
    SettingsStore.save()
  }

  @Mutation
  setTopWidgets(widgets: string[]): void {
    this.user_top_widgets = widgets
    SettingsStore.save()
  }

  // Secret mode for developers that know our secret.
  // Enabled by 10 clicks on the build date and when the pirate mode is enabled
  get is_dev_mode(): boolean {
    return this.is_pirate_mode && this.is_dev_mode_enabled
  }

  /**
   * Get name of the settings variable on the system
   * @param string name
   * @returns string
   */
  private static settingsName(name: string): string {
    return `bluerobotics-blueos-${name}`
  }

  /**
   * Get variable value from settings system
   * @param string name
   * @returns T
   */
  static loadVariable<T>(name: string): T {
    const storedVariable = window.localStorage.getItem(SettingsStore.settingsName(name))
    const castedVariable = storedVariable === null ? null : castString(storedVariable)
    return castedVariable as T
  }

  /**
   * Load all variables from settings system
   */
  static load(): void {
    Object.keys(SettingsStore.state).forEach((name: string) => {
      const value = SettingsStore.loadVariable(name)
      Vue.set(SettingsStore.state, name, value)
    })
  }

  /**
   * Save a variable on the settings system
   * @param string name
   * @param T value
   */
  static saveVariable<T>(name: string, value: T): void {
    // eslint-disable-next-line
    window.localStorage.setItem(SettingsStore.settingsName(name), JSON.stringify(value))
  }

  /**
   * Save all variables on the settings sytem
   */
  static save(): void {
    Object.entries(SettingsStore.state).forEach(([name, value]) => {
      SettingsStore.saveVariable(name, value)
    })
  }

  /**
   * Start the instance and do the proper connections
   */
  static start(): void {
    window.onstorage = () => {
      SettingsStore.load()
    }

    const settings_version: number = SettingsStore.loadVariable('settings_version')
    if (settings_version === null) {
      SettingsStore.save()
      return
    }

    SettingsStore.load()
  }
}

export { SettingsStore }

const settings: SettingsStore = getModule(SettingsStore)
SettingsStore.start()

export default settings
