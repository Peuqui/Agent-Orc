import { ref } from 'vue'
import { api } from '../api'
import { useSessions } from './useSessions'
import { useToast } from './useToast'

// Which answers of an agent were looked at: the time of the newest one seen. The server keeps it
// for every device and sends it with the session list; what this page marked counts here at once,
// before the list brings it back.
const markedHere = ref<Record<string, string>>({})

/** ISO times compare as text. */
export function seenUntil(sessionId: string): string {
  const server = useSessions().sessions.value.find((session) => session.id === sessionId)?.answers_seen ?? ''
  const here = markedHere.value[sessionId] ?? ''
  return here > server ? here : server
}

export function markSeen(sessionId: string, time: string): void {
  if (time <= seenUntil(sessionId)) return
  markedHere.value[sessionId] = time
  api.markAnswersSeen(sessionId, time).catch(useToast().error)
}
