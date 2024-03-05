import Vue from 'vue'
import {
  Action, getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { ActivePopup, PopupOptions, PopupResult } from '@/types/popups'

@Module({
  dynamic: true,
  store,
  name: 'popups',
})
class PopupsStore extends VuexModule {
  popups: Record<string, ActivePopup> = {}

  @Mutation
  addPopup(popup: ActivePopup): void {
    Vue.set(this.popups, popup.id, popup)
  }

  @Mutation
  removePopup(id: string): void {
    Vue.delete(this.popups, id)
  }

  @Mutation
  close(id: string): void {
    if (this.popups[id]) {
      this.popups[id].dismissed = true
      this.popups = { ...this.popups }
    }
  }

  @Mutation
  closeAll(): void {
    for (const id in this.popups) {
      this.popups[id].dismissed = true
    }

    this.popups = { ...this.popups }
  }

  @Action
  fire(options: PopupOptions): Promise<PopupResult> {
    return new Promise<PopupResult>((resolve) => {
      this.addPopup({
        id: options.id as string,
        dismissed: false,
        options,
        resolve: (result: PopupResult) => {
          this.removePopup(result.id)
          resolve(result)
        },
      })
    })
  }

  get popup_values(): ActivePopup[] {
    return Object.values(this.popups)
  }
}

export { PopupsStore }

const popups: PopupsStore = getModule(PopupsStore)
export default popups
