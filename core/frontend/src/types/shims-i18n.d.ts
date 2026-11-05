import { gettext, t } from 'ttag'

import { escapeHtml } from '@/i18n/escape'

declare module 'vue/types/vue' {
  interface Vue {
    t: typeof t
    gettext: typeof gettext
    escapeHtml: typeof escapeHtml
  }
}
