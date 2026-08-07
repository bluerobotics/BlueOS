import 'vue'

// vue-tour registers $tours on the Vue prototype (see main.ts).
declare module 'vue/types/vue' {
  interface Vue {
    $tours: Record<string, { start: () => void }>
  }
}
