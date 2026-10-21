import { type Ref, computed, reactive } from 'vue'

// Whether an agent's answers show every text it wrote, not only the last one of each request.
// Only held while the page is open and the agent exists: a reload, or a new agent in the same
// folder, starts with every text again, as no stored choice can follow an agent that is new.
const INITIAL = true
const chosen = reactive<Record<string, boolean>>({})

export function useAnswersAll(sessionId: string): Ref<boolean> {
  return computed({
    get: () => chosen[sessionId] ?? INITIAL,
    set: (all) => {
      chosen[sessionId] = all
    },
  })
}

/** The choice of an agent, read once (for a page that is not showing its answers). */
export function readAnswersAll(sessionId: string): boolean {
  return chosen[sessionId] ?? INITIAL
}

/** The agents that are gone take their choice with them. */
export function keepAnswersAllOf(existing: Set<string>): void {
  for (const sessionId of Object.keys(chosen)) {
    if (!existing.has(sessionId)) delete chosen[sessionId]
  }
}
