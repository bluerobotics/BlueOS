import { Module } from 'vuex-module-decorators'
import { ModuleOptions } from 'vuex-module-decorators/dist/types/moduleoptions'

// vuex-module-decorators@1.2.0 is incompatible with TypeScript 5's stricter decorator resolution:
// `Module({...})` binds to the void-returning overload, so the result must be cast to a ClassDecorator.
export function DynamicModule(options: ModuleOptions): ClassDecorator {
  return Module(options) as unknown as ClassDecorator
}
