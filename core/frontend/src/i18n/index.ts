import {
  addLocale, gettext, t, useLocale,
} from 'ttag'
import Vue from 'vue'
import es from 'vuetify/lib/locale/es'
import fr from 'vuetify/lib/locale/fr'
import ja from 'vuetify/lib/locale/ja'
import no from 'vuetify/lib/locale/no'
import pt from 'vuetify/lib/locale/pt'
import zhHans from 'vuetify/lib/locale/zh-Hans'

import vuetify from '@/plugins/vuetify'
import settings, { SettingsStore } from '@/store/settings'

import { escapeHtml } from './escape'

type Catalog = Parameters<typeof addLocale>[1]

const catalogs: Record<string, () => Promise<{ default: Catalog }>> = {
  pt_BR: () => import('./pt_BR.po.json'),
  es_ES: () => import('./es_ES.po.json'),
  fr_FR: () => import('./fr_FR.po.json'),
  ja_JP: () => import('./ja_JP.po.json'),
  no_NO: () => import('./no_NO.po.json'),
  zh_CN: () => import('./zh_CN.po.json'),
}

const vuetify_locales: Record<string, { id: string, messages: typeof pt }> = {
  pt_BR: { id: 'pt', messages: pt },
  es_ES: { id: 'es', messages: es },
  fr_FR: { id: 'fr', messages: fr },
  ja_JP: { id: 'ja', messages: ja },
  no_NO: { id: 'no', messages: no },
  zh_CN: { id: 'zh-Hans', messages: zhHans },
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

async function applyLocale(locale: string): Promise<void> {
  if (locale === 'en') {
    return
  }
  const catalog = await catalogs[locale]()
  addLocale(locale, catalog.default)
  useLocale(locale)
  const vuetify_locale = vuetify_locales[locale]
  if (vuetify_locale !== undefined) {
    vuetify.framework.lang.locales[vuetify_locale.id] = vuetify_locale.messages
    vuetify.framework.lang.current = vuetify_locale.id
  }
}

export async function initI18n(): Promise<string> {
  try {
    await SettingsStore.start()
  } catch (_error) {
    // Missing backend or bag settings should not block startup.
  }
  const locale = resolveLocale(settings.language)
  try {
    await applyLocale(locale)
  } catch (error) {
    // A catalog that fails to load should not block startup, English is used instead.
    console.warn(`Failed to load the ${locale} translations:`, error)
    return 'en'
  }
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
