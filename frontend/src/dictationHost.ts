// A workspace column is a page of its own in an iframe, and showing another workspace removes the
// iframes of the agents it does not hold: a dictation being transcribed there ended with its page.
// So the page at the top of the tab, which stays, does the transcribing. While the asking page is
// there, the text goes to it as before (into the field, sent at once if so set); once it is gone,
// into its agent's draft, where the agent's field finds it when it is shown again.
import { ApiError, api, type DictationDevice } from './api'
import { appendDictated } from './composables/useDrafts'
import { useToast } from './composables/useToast'

const HOST_KEY = 'agentOrcTranscribe'
type Transcribe = (sessionId: string, audio: Blob, device: DictationDevice, asking: Window) => Promise<string>

async function transcribe(sessionId: string, audio: Blob, device: DictationDevice, asking: Window): Promise<string> {
  try {
    const { text } = await api.dictate(audio, device)
    // A removed iframe's window reports itself closed.
    if (asking.closed && text) appendDictated(sessionId, text)
    return text
  } catch (error) {
    if (asking.closed) useToast().error(error)
    throw error
  }
}

/** Called once as the app starts: on the page at the top of the tab, the transcribing is done here. */
export function hostTranscription(): void {
  if (window.self === window.top) (window as unknown as Record<string, Transcribe>)[HOST_KEY] = transcribe
}

/** Transcribe a dictation for an agent's field on the page at the top of the tab. */
export async function transcribeForAgent(sessionId: string, audio: Blob, device: DictationDevice): Promise<string> {
  const top = (window.top ?? window) as unknown as Record<string, Transcribe>
  try {
    return await top[HOST_KEY](sessionId, audio, device, window)
  } catch (error) {
    // The top page's ApiError is another class than this page's: made anew, so it is shown as one.
    if (window.top === window || !(error instanceof Error) || !('code' in error)) throw error
    const { status, code, message, retryAfterSeconds } = error as ApiError
    throw new ApiError(status, code, message, retryAfterSeconds)
  }
}
