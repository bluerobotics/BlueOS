import { AlertRule } from "@/types/alerts"

type RuleInput<D extends Partial<AlertRule>> =
  Omit<AlertRule, keyof D> & Partial<Pick<AlertRule, keyof D & keyof AlertRule>>
export function ruleSet<D extends Partial<AlertRule>>(defaults: D) {
  return (rules: RuleInput<D>[]): AlertRule[] => rules.map((rule) => ({
    ...defaults,
    ...rule,
    inhibited_by: [...(defaults.inhibited_by ?? []), ...(rule.inhibited_by ?? [])],
  }) as AlertRule)
}