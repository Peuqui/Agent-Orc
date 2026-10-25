// A workspace column is a page of its own in an iframe, and showing another workspace removes the
// iframes of the agents it does not hold: a dictation being transcribed there ended with its page.
// So the page at the top of the tab, which stays, does the transcribing. While the asking page is
// there, the text goes to it as before (into the field, sent at once if so set); once it is gone,
// into its agent's draft. A field shown again meanwhile (the column opened anew) watches the agent's
// dictations: it says "transcribing" while one runs and takes the draft in when it is done.
import { ApiError, api, type DictationDevice } from './api'
import { appendDictated } from './composables/useDrafts'
import { useToast } from './composables/useToast'

const HOST_KEY = 'agentOrcTranscription'

interface Watcher {
  page: Window
  changed: (running: boolean) => void
}

interface Host {
  transcribe: (sessionId: string, audio: Blob, device: DictationDevice, asking: Window) => Promise<string>
  /** `changed` now and whenever a dictation of the agent starts or ends; returns the end of watching. */
  watch: (sessionId: string, page: Window, changed: (running: boolean) => void) => () => void
}

// Dictations of each agent being transcribed, and the fields watching them.
const running = new Map<string, number>()
const watchers = new Map<string, Set<Watcher>>()

function tell(sessionId: string): void {
  const now = (running.get(sessionId) ?? 0) > 0
  for (const watcher of watchers.get(sessionId) ?? []) {
    // A removed iframe's window reports itself closed; its functions may not be called any more.
    if (watcher.page.closed) watchers.get(sessionId)?.delete(watcher)
    else watcher.changed(now)
  }
}

async function transcribe(sessionId: string, audio: Blob, device: DictationDevice, asking: Window): Promise<string> {
  running.set(sessionId, (running.get(sessionId) ?? 0) + 1)
  tell(sessionId)
  try {
    const { text } = await api.dictate(audio, device)
    if (asking.closed && text) appendDictated(sessionId, text)
    return text
  } catch (error) {
    if (asking.closed) useToast().error(error)
    throw error
  } finally {
    running.set(sessionId, (running.get(sessionId) ?? 1) - 1)
    tell(sessionId)
  }
}

function watch(sessionId: string, page: Window, changed: (running: boolean) => void): () => void {
  const watcher = { page, changed }
  if (!watchers.has(sessionId)) watchers.set(sessionId, new Set())
  watchers.get(sessionId)?.add(watcher)
  changed((running.get(sessionId) ?? 0) > 0)
  return () => watchers.get(sessionId)?.delete(watcher)
}

/** Called once as the app starts: on the page at the top of the tab, the transcribing is done here. */
export function hostTranscription(): void {
  if (window.self === window.top) (window as unknown as Record<string, Host>)[HOST_KEY] = { transcribe, watch }
}

function host(): Host {
  return ((window.top ?? window) as unknown as Record<string, Host>)[HOST_KEY]
}

/** Transcribe a dictation for an agent's field on the page at the top of the tab. */
export async function transcribeForAgent(sessionId: string, audio: Blob, device: DictationDevice): Promise<string> {
  try {
    return await host().transcribe(sessionId, audio, device, window)
  } catch (error) {
    // An error of the top page is of its classes, not of this page's (not even `instanceof Error`):
    // an ApiError is made anew from its fields, so it is shown as one.
    if (window.top === window || typeof error !== 'object' || error === null || !('code' in error)) throw error
    const { status, code, message, retryAfterSeconds } = error as ApiError
    throw new ApiError(status, code, message, retryAfterSeconds)
  }
}

/** Follow the agent's dictations wherever they were started in this tab; returns the end of it. */
export function watchTranscriptions(sessionId: string, changed: (running: boolean) => void): () => void {
  return host().watch(sessionId, window, changed)
}
