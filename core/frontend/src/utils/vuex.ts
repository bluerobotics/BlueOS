import { Module } from 'vuex-module-decorators'

// vuex-module-decorators 1.x is incompatible with TypeScript 5's stricter decorator resolution:
// `Module({...})` binds to the void-returning overload, so the result must be cast to a ClassDecorator.
export function DynamicModule(options: Parameters<typeof Module>[0]): ClassDecorator {
  return Module(options) as unknown as ClassDecorator
}
