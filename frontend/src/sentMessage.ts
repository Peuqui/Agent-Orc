// Something was sent to an agent: the page that polls the agents asks again at once, and quickly for a short while,
// until the conversation shows it (useSessions). A workspace column is a page of its own in an iframe that does not poll
// (see useSessions), so it tells the page around it.
import { COLUMN_TAB } from './device'

const SENT_MESSAGE = 'agent-orc-sent'
const listeners = new Set<() => void>()

/** Called when a message was sent from this page or from a column of it; returns what stops it. */
export function onMessageSent(listener: () => void): () => void {
  listeners.add(listener)
  const fromColumn = (event: MessageEvent<{ kind?: string }>): void => {
    if (event.origin === location.origin && event.data?.kind === SENT_MESSAGE) listener()
  }
  window.addEventListener('message', fromColumn)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('message', fromColumn)
  }
}

/** To be called when a message to an agent was accepted by the server. */
export function messageSent(): void {
  if (COLUMN_TAB !== null) window.parent.postMessage({ kind: SENT_MESSAGE }, location.origin)
  else listeners.forEach((listener) => listener())
}
