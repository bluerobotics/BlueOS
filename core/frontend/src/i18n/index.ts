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

const language_names: Record<string, string> = {
  en: 'English',
  pt_BR: 'Português',
  es_ES: 'Español',
  fr_FR: 'Français',
  ja_JP: '日本語',
  no_NO: 'Norsk',
  zh_CN: '中文',
}

export function resolveLocale(value: unknown): string {
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

export const available_languages = ['en', ...Object.keys(catalogs)].map((id) => ({
  id,
  name: language_names[id] ?? id,
}))

export { escapeHtml, gettext, t }

export default {
  install(vue: typeof Vue): void {
    vue.prototype.t = t
    vue.prototype.gettext = gettext
    vue.prototype.escapeHtml = escapeHtml
  },
}
