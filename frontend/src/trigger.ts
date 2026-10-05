// The control the user pressed last (pointer or keyboard): a dialog it opens appears right
// beside it instead of far away on a large screen (BaseDialog). Remembered at the press itself,
// as Safari gives buttons no focus when they are clicked.
const CONTROLS = 'button, a, input, select, textarea, [role="button"]'

// A press often closes the menu or dialog its control sits in, just as it opens the next
// dialog: the control is gone by then, but its place on screen still counts for this long.
const GONE_CONTROL_GRACE_MS = 1000

let lastTrigger: Element | null = null
let lastRect: DOMRect | null = null
let pressedAt = 0

function remember(target: EventTarget | null): void {
  if (!(target instanceof Element)) return
  lastTrigger = target.closest(CONTROLS) ?? target
  lastRect = lastTrigger.getBoundingClientRect()
  pressedAt = performance.now()
}

document.addEventListener('pointerdown', (event) => remember(event.target), true)
document.addEventListener('keydown', () => remember(document.activeElement), true)

/** Where the last pressed control is (or just was) on screen; null if there is none. */
export function triggerRect(): DOMRect | null {
  if (lastTrigger?.isConnected) return lastTrigger.getBoundingClientRect()
  return performance.now() - pressedAt < GONE_CONTROL_GRACE_MS ? lastRect : null
}
