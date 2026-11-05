// The badge beside the pointer while a dictation runs (DictationPointer.vue) is the tab's, not a column's: a
// workspace column is a page of its own in an iframe, and its badge stopped at the column's edge, so it looked
// as if the dictation had ended. The page at the top of the tab draws it; every page says when its dictation
// runs and hands its pointer moves up, in the top page's coordinates. A page cannot draw outside the browser.
import { reactive } from 'vue'

const HOST_KEY = 'agentOrcDictationPointer'

interface Running {
  page: Window
  listening: boolean
}

interface Host {
  /** What the badge shows: whether one runs, whether it takes speech in (else it is transcribed), where. */
  state: { shown: boolean; listening: boolean; x: number; y: number }
  /** A dictation of `page` runs (listening) or is transcribed; null: it ended. */
  set: (id: symbol, page: Window, listening: boolean | null) => void
  move: (x: number, y: number) => void
}

function createHost(): Host {
  const state = reactive({ shown: false, listening: false, x: 0, y: 0 })
  const running = new Map<symbol, Running>()

  function show(): void {
    // A removed column's page reports itself closed: its dictation ended with it.
    for (const [id, entry] of running) if (entry.page.closed) running.delete(id)
    state.shown = running.size > 0
    state.listening = [...running.values()].some((entry) => entry.listening)
  }

  return {
    state,
    set(id, page, listening) {
      if (listening === null) running.delete(id)
      else running.set(id, { page, listening })
      show()
    },
    move(x, y) {
      state.x = x
      state.y = y
    },
  }
}

/** Called once as the app starts: the page at the top of the tab draws the badge (App.vue). */
export function hostDictationPointer(): void {
  if (window.self === window.top) (window as unknown as Record<string, Host>)[HOST_KEY] = createHost()
}

function host(): Host {
  return ((window.top ?? window) as unknown as Record<string, Host>)[HOST_KEY]
}

/** The badge's state, for the page at the top of the tab. */
export function dictationPointerState(): Host['state'] {
  return host().state
}

/** Where this page's (x, y) is on the page at the top of the tab: past the frames it sits in. */
function onTop(x: number, y: number): { x: number; y: number } {
  let frame: Window = window
  while (frame !== frame.parent && frame.frameElement !== null) {
    const box = frame.frameElement.getBoundingClientRect()
    x += box.left
    y += box.top
    frame = frame.parent
  }
  return { x, y }
}

/** Called once as the app starts, on every page: its pointer moves go up while a dictation runs anywhere. */
export function reportPointerMoves(): void {
  window.addEventListener(
    'pointermove',
    (event) => {
      const badge = host()
      if (!badge.state.shown) return
      const { x, y } = onTop(event.clientX, event.clientY)
      badge.move(x, y)
    },
    { passive: true },
  )
}

/** A dictation of this page: `set` it running (listening or transcribed) or ended (null), from where the pointer
 * pressed (this page's coordinates). */
export function dictationPointer(): { set: (listening: boolean | null, x?: number, y?: number) => void } {
  const id = Symbol('dictation')
  return {
    set(listening, x, y) {
      const badge = host()
      if (x !== undefined && y !== undefined) {
        const start = onTop(x, y)
        badge.move(start.x, start.y)
      }
      badge.set(id, window, listening)
    },
  }
}
