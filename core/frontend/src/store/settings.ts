import Vue from 'vue'
import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import beacon from '@/store/beacon'
import { castString } from '@/utils/helper_functions'
import bag from '@/store/bag'

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
   * Get variable value from settings system
   * @param string name
   * @returns T
   */
  static async loadVariable<T>(name: string): Promise<T | null> {
    const data = await bag.getData(`settings/${name}`)
    return data as T ?? null
  }

  /**
   * Load all variables from settings system
   */
  static async load(): Promise<void> {
    const data = await bag.getData('settings')
    if (!data) {
      console.warn('No settings data found')
      return
    }
    Object.entries(data).forEach(([name, value]) => {
      Vue.set(SettingsStore.state, name, value)
    })
  }

  /**
   * Save all variables on the settings system
   */
  static async save(): Promise<void> {
    await bag.setData('settings', SettingsStore.state)
  }

  /**
   * Start the instance and do the proper connections
   */
  static async start(): Promise<void> {
    const settings_version = await SettingsStore.loadVariable<number>('settings_version')
    if (settings_version === null) {
      await SettingsStore.save()
      return
    }

    await SettingsStore.load()
  }
}

export { SettingsStore }

const settings: SettingsStore = getModule(SettingsStore)
SettingsStore.start()

export default settings
