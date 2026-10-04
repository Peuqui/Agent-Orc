// The control the user pressed last (pointer or keyboard): a dialog it opens appears right
// beside it instead of far away on a large screen (BaseDialog). Remembered at the press itself,
// as Safari gives buttons no focus when they are clicked.
const CONTROLS = 'button, a, input, select, textarea, [role="button"]'

let lastTrigger: Element | null = null

function remember(target: EventTarget | null): void {
  if (target instanceof Element) lastTrigger = target.closest(CONTROLS) ?? target
}

document.addEventListener('pointerdown', (event) => remember(event.target), true)
document.addEventListener('keydown', () => remember(document.activeElement), true)

/** Where the last pressed control is on screen; null if there is none (any more). */
export function triggerRect(): DOMRect | null {
  return lastTrigger?.isConnected ? lastTrigger.getBoundingClientRect() : null
}
