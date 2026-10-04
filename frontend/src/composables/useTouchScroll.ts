// Finger scrolling for a view that scrolls in steps (the terminal: tmux scrolls on wheel
// events). The swipe is turned into steps while the finger moves; when it is lifted, the
// scroll keeps going at the finger's speed and slows down, like native scrolling on a phone.

const PIXELS_PER_STEP = 24
// Weight of the newest movement in the measured speed; the rest is the speed so far, which
// smooths out jittery touch events.
const NEWEST_SPEED_WEIGHT = 0.7
// Speed left after one millisecond of gliding: 0.997^16 ≈ 0.95 per frame.
const GLIDE_FRICTION_PER_MS = 0.997
// Below this speed (pixels per millisecond) the glide ends.
const MIN_GLIDE_SPEED = 0.05
// A finger resting this long before it is lifted means "stop here", not a flick.
const MAX_RELEASE_PAUSE_MS = 80
// After this many pixels the swipe's direction is settled: up and down scroll, sideways not.
const AXIS_LOCK_PX = 10
// A sideways swipe at least this long, and clearly more sideways than up or down, is reported.
const MIN_SIDEWAYS_SWIPE_PX = 60
const SIDEWAYS_RATIO = 2

/**
 * scroll receives whole steps (positive: towards newer content) and the finger position;
 * sideways, if given, a finished sideways swipe (1: to the left, i.e. "next"; -1: "previous").
 */
export function useTouchScroll(
  scroll: (steps: number, x: number, y: number) => void,
  sideways?: (direction: 1 | -1) => void,
) {
  let lastY: number | null = null
  let startX = 0
  let startY = 0
  let axis: 'vertical' | 'sideways' | null = null
  let lastTime = 0
  let x = 0
  // Pixels per millisecond; positive while the finger moves up.
  let speed = 0
  let remainder = 0
  let glideFrame: number | null = null

  function addDistance(pixels: number): void {
    remainder += pixels
    const steps = Math.trunc(remainder / PIXELS_PER_STEP)
    if (steps === 0) return
    // Keep the rest, so slow swipes still add up to steps.
    remainder -= steps * PIXELS_PER_STEP
    scroll(steps, x, lastY ?? 0)
  }

  function stopGlide(): void {
    if (glideFrame !== null) cancelAnimationFrame(glideFrame)
    glideFrame = null
  }

  function glide(): void {
    let previous = performance.now()
    const frame = (now: number): void => {
      const elapsed = now - previous
      previous = now
      addDistance(speed * elapsed)
      speed *= GLIDE_FRICTION_PER_MS ** elapsed
      glideFrame = Math.abs(speed) < MIN_GLIDE_SPEED ? null : requestAnimationFrame(frame)
    }
    glideFrame = requestAnimationFrame(frame)
  }

  function onTouchStart(event: TouchEvent): void {
    // Touching a gliding view stops it, as on a phone.
    stopGlide()
    if (event.touches.length !== 1) {
      lastY = null
      return
    }
    lastY = event.touches[0].clientY
    x = event.touches[0].clientX
    startX = x
    startY = lastY
    axis = null
    lastTime = event.timeStamp
    speed = 0
    remainder = 0
  }

  function onTouchMove(event: TouchEvent): void {
    if (lastY === null || event.touches.length !== 1) return
    const touch = event.touches[0]
    if (axis === null) {
      const dx = Math.abs(touch.clientX - startX)
      const dy = Math.abs(touch.clientY - startY)
      if (Math.max(dx, dy) < AXIS_LOCK_PX) return
      axis = sideways && dx > dy ? 'sideways' : 'vertical'
    }
    if (axis === 'sideways') {
      // Not a scroll, and not a pan of the page either.
      event.preventDefault()
      x = touch.clientX
      lastY = touch.clientY
      return
    }
    const distance = lastY - touch.clientY
    if (distance === 0) return
    // The swipe must not also scroll or zoom the page.
    event.preventDefault()
    const elapsed = event.timeStamp - lastTime
    if (elapsed > 0) {
      speed = NEWEST_SPEED_WEIGHT * (distance / elapsed) + (1 - NEWEST_SPEED_WEIGHT) * speed
    }
    lastY = touch.clientY
    x = touch.clientX
    lastTime = event.timeStamp
    addDistance(distance)
  }

  function onTouchEnd(event: TouchEvent): void {
    if (axis === 'sideways') {
      const dx = x - startX
      const dy = (lastY ?? startY) - startY
      if (Math.abs(dx) >= MIN_SIDEWAYS_SWIPE_PX && Math.abs(dx) > SIDEWAYS_RATIO * Math.abs(dy)) {
        sideways?.(dx < 0 ? 1 : -1)
      }
      lastY = null
      return
    }
    const flicked =
      lastY !== null &&
      event.timeStamp - lastTime <= MAX_RELEASE_PAUSE_MS &&
      Math.abs(speed) >= MIN_GLIDE_SPEED
    if (flicked) glide()
    else lastY = null
  }

  return { onTouchStart, onTouchMove, onTouchEnd, stopGlide }
}
