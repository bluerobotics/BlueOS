import { effectScope, watch } from 'vue'

import alerts from '@/store/alerts'
import notifications from '@/store/notifications'
import { AlertLifecycle, AlertRule, AlertRuleId } from '@/types/alerts'
import { LiveNotification } from '@/types/notifications'

class AlertEngine {
  private static instance: AlertEngine

  private rules: Map<AlertRuleId, AlertRule> = new Map()

  private scope = effectScope(true)

  /* A rule only ever waits for one next step (fire, time out or drop), so one timer per rule is enough */
  private scheduled: Map<AlertRuleId, ReturnType<typeof setTimeout>> = new Map()

  private constructor() { }

  public static getInstance(): AlertEngine {
    if (!AlertEngine.instance) {
      AlertEngine.instance = new AlertEngine()
    }
    return AlertEngine.instance
  }

  public getRule(id: string): AlertRule | undefined {
    return this.rules.get(id as AlertRuleId)
  }

  public getRules(): AlertRule[] {
    return Array.from(this.rules.values())
  }

  public register(rules: AlertRule[]): void {
    for (const rule of rules) {
      if (this.rules.has(rule.id)) {
        console.error(`Alert rule ${rule.id} is already registered`)
        continue
      }
      this.rules.set(rule.id, rule)
      this.scope.run(() => {
        watch(
          () => this.evaluateRule(rule),
          (result) => this.transitionRule(rule, result),
          { immediate: true },
        )
      })
    }
  }

  public dismiss(id: string): void {
    const rule = this.getRule(id)
    if (!rule) {
      return
    }
    this.cancel(rule.id)
    this.setAlertState(rule.id, AlertLifecycle.Dismissed)
  }

  private evaluateRule(rule: AlertRule): boolean | undefined {
    if (rule.inhibited_by?.some((id) => alerts.alerts[id] !== undefined)) {
      return undefined
    }
    try {
      return rule.condition()
    } catch {
      return undefined
    }
  }

  private transitionRule(rule: AlertRule, condition: boolean | undefined): void {
    /* undefined means that the rule is not ready to be evaluated yet or there was an error evaluating it */
    if (condition === undefined) {
      this.dropAlert(rule.id)
      return
    }

    const state = alerts.alerts[rule.id]?.state

    if (condition) {
      if (state === undefined) {
        this.startPending(rule)
      } else if (state === AlertLifecycle.Fired) {
        // Condition is back during keep_firing_filter_ms: cancels the drop and restarts the timeout
        this.scheduleTimeOut(rule)
      }
      // pending: already waiting to fire. timed_out: stays until the condition clears
      return
    }

    if (state === AlertLifecycle.Fired && rule.keep_firing_filter_ms) {
      this.schedule(rule.id, rule.keep_firing_filter_ms, () => this.dropAlert(rule.id))
      return
    }
    this.dropAlert(rule.id)
  }

  private startPending(rule: AlertRule): void {
    if (!rule.pending_ms) {
      this.fireAlert(rule)
      return
    }
    this.setAlertState(rule.id, AlertLifecycle.Pending)
    this.schedule(rule.id, rule.pending_ms, () => this.fireAlert(rule))
  }

  private fireAlert(rule: AlertRule): void {
    this.setAlertState(rule.id, AlertLifecycle.Fired)
    this.scheduleTimeOut(rule)
  }

  private scheduleTimeOut(rule: AlertRule): void {
    if (rule?.timeout_ms && rule.timeout_ms > 100) {
      this.schedule(rule.id, rule.timeout_ms, () => this.timeOutAlert(rule.id))
      return
    }
    this.cancel(rule.id)
  }

  private timeOutAlert(id: AlertRuleId): void {
    const current = alerts.alerts[id]
    if (current) {
      alerts.setAlert({ ...current, state: AlertLifecycle.TimedOut })
      this.logEvent(id, AlertLifecycle.TimedOut)
    }
  }

  private dropAlert(id: AlertRuleId): void {
    this.cancel(id)
    if (alerts.alerts[id] !== undefined) {
      this.logEvent(id, 'cleared')
    }
    alerts.removeAlert(id)
  }

  private setAlertState(id: AlertRuleId, state: AlertLifecycle): void {
    alerts.setAlert({
      rule_id: id,
      state,
      since: new Date(),
    })
    this.logEvent(id, state)
  }

  private logEvent(id: AlertRuleId, event: AlertLifecycle | 'cleared'): void {
    const rule = this.getRule(id)
    if (!rule) {
      return
    }
    const notification = new LiveNotification(rule.level, rule.service, 'alert', `${id} ${event}`)
    notifications.pushNotification(notification)
  }

  /* Replaces whatever was scheduled before, so a timer can never outlive the state it was created for */
  private schedule(id: AlertRuleId, delay_ms: number, action: () => void): void {
    this.cancel(id)
    this.scheduled.set(id, setTimeout(() => {
      this.scheduled.delete(id)
      action()
    }, delay_ms))
  }

  private cancel(id: AlertRuleId): void {
    clearTimeout(this.scheduled.get(id))
    this.scheduled.delete(id)
  }
}

const alert_engine = AlertEngine.getInstance()

export default alert_engine
