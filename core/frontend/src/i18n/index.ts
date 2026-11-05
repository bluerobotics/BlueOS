import {
  addLocale, gettext, t, useLocale,
} from 'ttag'
import Vue from 'vue'
import pt from 'vuetify/lib/locale/pt'

import vuetify from '@/plugins/vuetify'
import settings, { SettingsStore } from '@/store/settings'

import { escapeHtml } from './escape'
import pt_BR from './pt_BR.po.json'

const catalogs: Record<string, typeof pt_BR> = {
  pt_BR,
}

function resolveLocale(value: unknown): string {
  if (typeof value !== 'string') {
    return 'en'
  }
  if (value === 'en' || catalogs[value] !== undefined) {
    return value
  }
  return 'en'
}

function applyLocale(locale: string): void {
  if (locale === 'en') {
    return
  }
  addLocale(locale, catalogs[locale])
  useLocale(locale)
  if (locale === 'pt_BR') {
    vuetify.framework.lang.locales.pt = pt
    vuetify.framework.lang.current = 'pt'
  }
}

export async function initI18n(): Promise<string> {
  try {
    await SettingsStore.start()
  } catch (_error) {
    // Missing backend or bag settings should not block startup.
  }
  const locale = resolveLocale(settings.language)
  applyLocale(locale)
  return locale
}

export { escapeHtml, gettext, t }

export default {
  install(vue: typeof Vue): void {
    vue.prototype.t = t
    vue.prototype.gettext = gettext
    vue.prototype.escapeHtml = escapeHtml
  },
}
