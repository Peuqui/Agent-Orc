// A finger that rests on an element without moving: the long press of phones (it selects text
// there, wherever the text is real).
const LONG_PRESS_MS = 500
// A finger moves a little even when it rests; further than this it is a swipe, not a press.
const MOVE_TOLERANCE_PX = 10

/** Calls action once a single finger has rested on the element for a while. */
export function onLongPress(element: HTMLElement, action: () => void): void {
  let timer: number | undefined
  let startX = 0
  let startY = 0

  function cancel(): void {
    window.clearTimeout(timer)
  }

  element.addEventListener(
    'touchstart',
    (event) => {
      cancel()
      if (event.touches.length !== 1) return
      startX = event.touches[0].clientX
      startY = event.touches[0].clientY
      timer = window.setTimeout(action, LONG_PRESS_MS)
    },
    { passive: true },
  )
  element.addEventListener(
    'touchmove',
    (event) => {
      const touch = event.touches[0]
      if (Math.hypot(touch.clientX - startX, touch.clientY - startY) > MOVE_TOLERANCE_PX) cancel()
    },
    { passive: true },
  )
  element.addEventListener('touchend', cancel, { passive: true })
  element.addEventListener('touchcancel', cancel, { passive: true })
}
