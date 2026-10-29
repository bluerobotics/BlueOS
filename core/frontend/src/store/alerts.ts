import Vue from 'vue'
import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { Alert, AlertLifecycle, AlertRuleId } from '@/types/alerts'

@Module({
  dynamic: true,
  store,
  name: 'alerts',
})

class AlertsStore extends VuexModule {
  alerts: Record<string, Alert> = {}

  @Mutation
  setAlert(alert: Alert): void {
    Vue.set(this.alerts, alert.rule_id, alert)
  }

  @Mutation
  removeAlert(id: AlertRuleId): void {
    Vue.delete(this.alerts, id)
  }

  get alerts_list(): Alert[] {
    return Object.values(this.alerts)
  }

  get fired_alerts(): Alert[] {
    return this.alerts_list.filter((alert) => alert.state === AlertLifecycle.Fired)
  }

  get isFired(): (id: AlertRuleId) => boolean {
    return (id: AlertRuleId) => this.alerts[id]?.state === AlertLifecycle.Fired
  }
}

export { AlertsStore }

const alerts: AlertsStore = getModule(AlertsStore)

export default alerts
