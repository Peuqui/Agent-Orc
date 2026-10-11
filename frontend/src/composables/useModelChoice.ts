import { useI18n } from 'vue-i18n'
import type { ModelChoice } from '../api'
import type { SelectOption } from '../components/SelectMenu.vue'

// The model last chosen for a profile is offered first the next time.
const LAST_MODEL_KEY = 'agent-orc-last-model:'

export function rememberModel(profile: string, model: string): void {
  localStorage.setItem(LAST_MODEL_KEY + profile, model)
}

/** The model chosen last for the profile if it is still on offer, otherwise the first one. */
export function preferredModel(profile: string, offered: string[]): string | null {
  const last = localStorage.getItem(LAST_MODEL_KEY + profile)
  return last !== null && offered.includes(last) ? last : (offered[0] ?? null)
}

// A note that is the last day a model is free (the backend command writes it, see
// agent_orc/backends.py FREE_UNTIL_PREFIX); other notes are shown as they are.
export const FREE_UNTIL_PREFIX = 'free_until='
const MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000

/** The days from `today` to the day `until` (YYYY-MM-DD), by calendar days. */
export function daysUntil(until: string, today: Date): number {
  const [year, month, day] = until.split('-').map(Number)
  const end = Date.UTC(year, month - 1, day)
  const start = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((end - start) / MILLISECONDS_PER_DAY)
}

/** Words a note in the language of the interface: "free until 24 Nov (44 days left)". */
export function useModelNote(): (note: string) => string {
  const { t, locale } = useI18n()
  return (note) => {
    if (!note.startsWith(FREE_UNTIL_PREFIX)) return note
    const until = note.slice(FREE_UNTIL_PREFIX.length)
    const [year, month, day] = until.split('-').map(Number)
    const date = new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short' }).format(new Date(year, month - 1, day))
    const days = daysUntil(until, new Date())
    return t('models.freeUntil', { date, count: days }, days)
  }
}

/** The models as the entries of a choice: the name, and its note (worded by `describe`) after a
 * dash where it has one. */
export function modelOptions(models: ModelChoice[], describe: (note: string) => string): SelectOption[] {
  return models.map((choice) => ({
    value: choice.name,
    label: choice.note ? `${choice.name} – ${describe(choice.note)}` : choice.name,
  }))
}
