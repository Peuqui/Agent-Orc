import { type Ref, computed } from 'vue'
import { api } from '../api'
import { useSessions } from './useSessions'
import { useToast } from './useToast'

// Whether an agent's answers show every text it wrote, not only the last one of each request.
// The server keeps it for every device and sends it with the session list, until the agent's
// session ends: a new agent, even in the same folder, shows every text again.

/** The choice of an agent, read once (for a page that is not showing its answers). */
export function readAnswersAll(sessionId: string): boolean {
  return useSessions().sessions.value.find((session) => session.id === sessionId)?.answers_all ?? true
}

export function useAnswersAll(sessionId: string): Ref<boolean> {
  const { refresh } = useSessions()
  return computed({
    get: () => readAnswersAll(sessionId),
    set: (all) => {
      api.setAnswersMode(sessionId, all).then(refresh, useToast().error)
    },
  })
}
