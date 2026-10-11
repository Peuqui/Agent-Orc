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

/** The models as the entries of a choice: the name, and its note after a dash where it has one. */
export function modelOptions(models: ModelChoice[]): SelectOption[] {
  return models.map((choice) => ({ value: choice.name, label: choice.note ? `${choice.name} – ${choice.note}` : choice.name }))
}
