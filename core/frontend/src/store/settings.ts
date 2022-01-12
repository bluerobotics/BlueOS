import Vue from 'vue'
import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'

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

    @Mutation
    setDarkTheme(value: boolean): void {
      this.is_dark_theme = value
      SettingsStore.save()
    }

    @Mutation
    setPirateMode(value: boolean): void {
      this.is_pirate_mode = value
      SettingsStore.save()
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
      return (window.localStorage.getItem(SettingsStore.settingsName(name)) as unknown) as T
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
      window.localStorage.setItem(SettingsStore.settingsName(name), value as any)
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
