declare module '*.glb' {
  const value: string
  export default value
}

declare module 'vue-tooltip-directive'

declare module '@/assets/colors/default'
declare module '@/assets/colors/blue_robotics'
declare module '@/assets/colors/vuetify'

declare module '@/style/colors/default'
declare module '@/style/colors/blue_robotics'
declare module '@/style/colors/vuetify'

declare module 'colorthief'

// `require(...)` in templates is rewritten to asset imports by
// vue-template-babel-compiler; `process.env` is replaced by Vite's `define`.
declare function require(path: string): string

declare const process: {
  env: Record<string, string | undefined>
}
