// Where the STT-Suite stands (whether there is one, its language, whether a model sits on the GPU) is one for the
// whole tab, but every dictation field asked for itself: as it opened and after its own dictation. A workspace
// column is a page of its own in an iframe, so after a dictation had loaded the GPU model only the button of that
// column showed the GPU; the others kept what they had seen as they opened. So the page at the top of the tab asks
// the service and keeps the one timer for the GPU worker's end; every page watches what it finds, and any field
// may ask it to look again.
import type { DictationService } from './api'

/** The server's answer about dictation (GET dictation). */
export interface DictationServiceState {
  language: string
  stt: boolean
  service: DictationService | null
}

interface Watcher {
  page: Window
  changed: (state: DictationServiceState) => void
}

export interface DictationServiceHost {
  /** Ask the service anew; every watching page hears the answer. */
  refresh: () => Promise<void>
  /** `changed` now if the state is known, and with every answer after; returns the end of watching. */
  watch: (page: Window, changed: (state: DictationServiceState) => void) => () => void
}

const HOST_KEY = 'agentOrcDictationService'

export function createServiceHost(
  fetchState: () => Promise<DictationServiceState>,
  onError: (error: unknown) => void,
): DictationServiceHost {
  let known: DictationServiceState | null = null
  const watchers = new Set<Watcher>()
  // The idle GPU worker ends itself after a time the service reports: asked again when that is over, the answer
  // says whether someone else used the GPU meanwhile (the time starts anew) or the model is gone.
  let unloadCheck: ReturnType<typeof setTimeout> | undefined

  function tell(state: DictationServiceState): void {
    for (const watcher of watchers) {
      // A removed iframe's window reports itself closed; its functions may not be called any more.
      if (watcher.page.closed) watchers.delete(watcher)
      else watcher.changed(state)
    }
  }

  function refresh(): Promise<void> {
    return fetchState()
      .then((state) => {
        known = state
        clearTimeout(unloadCheck)
        const remaining = state.service?.gpu_ttl_remaining_seconds
        if (state.service?.gpu_loaded && remaining != null) {
          unloadCheck = setTimeout(() => void refresh(), (remaining + 1) * 1000)
        }
        tell(state)
      })
      .catch(onError)
  }

  function watch(page: Window, changed: (state: DictationServiceState) => void): () => void {
    const watcher = { page, changed }
    watchers.add(watcher)
    if (known !== null) changed(known)
    return () => watchers.delete(watcher)
  }

  return { refresh, watch }
}

/** Called once as the app starts: on the page at the top of the tab, the service is asked here. */
export function hostDictationService(
  fetchState: () => Promise<DictationServiceState>,
  onError: (error: unknown) => void,
): void {
  if (window.self === window.top) {
    ;(window as unknown as Record<string, DictationServiceHost>)[HOST_KEY] = createServiceHost(fetchState, onError)
  }
}

function host(): DictationServiceHost {
  return ((window.top ?? window) as unknown as Record<string, DictationServiceHost>)[HOST_KEY]
}

/** Follow the service's state as the page at the top of the tab finds it; returns the end of it. */
export function watchDictationService(changed: (state: DictationServiceState) => void): () => void {
  return host().watch(window, changed)
}

/** Have the service asked anew: as a field opens and after a dictation, which may have loaded or found gone the
 * GPU model. Every field of the tab sees the answer. */
export function refreshDictationService(): Promise<void> {
  return host().refresh()
}
