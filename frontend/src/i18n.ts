import { createI18n } from 'vue-i18n'
import de from './locales/de.json'
import en from './locales/en.json'

export const LOCALES = ['de', 'en'] as const
export type Locale = (typeof LOCALES)[number]

const STORAGE_KEY = 'agent-orc-locale'

function isLocale(value: string | null): value is Locale {
  return LOCALES.some((locale) => locale === value)
}

function initialLocale(): Locale {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (isLocale(stored)) return stored
  return navigator.language.toLowerCase().startsWith('de') ? 'de' : 'en'
}

const startLocale = initialLocale()

export const i18n = createI18n({
  legacy: false,
  locale: startLocale,
  messages: { de, en },
})
// index.html says "de"; the page is in the language chosen.
document.documentElement.lang = startLocale

function applyLocale(locale: Locale): void {
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
}

export function setLocale(locale: Locale): void {
  applyLocale(locale)
  localStorage.setItem(STORAGE_KEY, locale)
}

// The workspace's columns are pages of their own: the language chosen in one document reaches the
// others through the storage, whose event only the other documents get (27.11.: the waiting line in
// a column stayed in the old language until the column was loaded again).
window.addEventListener('storage', (event) => {
  if (event.key === STORAGE_KEY && isLocale(event.newValue)) applyLocale(event.newValue)
})
