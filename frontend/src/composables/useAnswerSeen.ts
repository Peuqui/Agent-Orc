// Which answers of an agent were looked at: the time of the newest one seen, kept on this device.
const SEEN_KEY = 'agent-orc-answers-seen:'

export function seenUntil(sessionId: string): string {
  return localStorage.getItem(SEEN_KEY + sessionId) ?? ''
}

/** ISO times compare as text. */
export function markSeen(sessionId: string, time: string): void {
  if (time > seenUntil(sessionId)) localStorage.setItem(SEEN_KEY + sessionId, time)
}
