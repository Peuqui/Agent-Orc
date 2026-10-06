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
