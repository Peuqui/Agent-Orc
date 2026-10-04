import { ref } from 'vue'

// Rearranging items by dragging them with a mouse or a finger: the dragged item takes the place
// of the item it is dropped on (the others move up). A mouse drag starts after a short
// movement, so a click stays a click; a finger first holds the item for a moment, so swiping
// across the items still scrolls the page.
const DRAG_THRESHOLD_PX = 8
const TOUCH_HOLD_MS = 400

interface Drag {
  id: string
  pointerId: number
  startX: number
  startY: number
  /** False until the pointer has moved (mouse) or was held (finger) long enough. */
  active: boolean
  /** The item whose place it takes when dropped. */
  target: string | null
}

export interface ReorderOptions {
  /** The item at a screen position, or null. */
  targetAt: (x: number, y: number) => string | null
  onDrop: (id: string, target: string) => void
  /** Elements inside an item where a press must not start a drag (its own controls). */
  ignore: string
}

/** Move id to the place of target in a list (the others move up). */
export function moveInList(list: string[], id: string, target: string): void {
  const to = list.indexOf(target)
  list.splice(list.indexOf(id), 1)
  list.splice(to, 0, id)
}

export function useReorder(options: ReorderOptions) {
  const drag = ref<Drag | null>(null)
  let holdTimer: number | undefined

  function start(element: HTMLElement): void {
    if (drag.value === null) return
    drag.value.active = true
    // Keeps the pointer events coming while the pointer leaves the item.
    element.setPointerCapture(drag.value.pointerId)
  }

  function end(): void {
    window.clearTimeout(holdTimer)
    drag.value = null
  }

  function onPointerDown(event: PointerEvent, id: string): void {
    if (event.button !== 0 || (event.target as Element).closest(options.ignore)) return
    const element = event.currentTarget as HTMLElement
    const { pointerId, clientX, clientY } = event
    drag.value = { id, pointerId, startX: clientX, startY: clientY, active: false, target: null }
    if (event.pointerType === 'touch') holdTimer = window.setTimeout(() => start(element), TOUCH_HOLD_MS)
  }

  function onPointerMove(event: PointerEvent): void {
    const current = drag.value
    if (current === null || event.pointerId !== current.pointerId) return
    if (!current.active) {
      const moved = Math.hypot(event.clientX - current.startX, event.clientY - current.startY)
      if (moved < DRAG_THRESHOLD_PX) return
      // A finger moving before the hold is up scrolls instead.
      if (event.pointerType === 'touch') return end()
      start(event.currentTarget as HTMLElement)
    }
    current.target = options.targetAt(event.clientX, event.clientY)
  }

  function onPointerUp(event: PointerEvent): void {
    const current = drag.value
    if (current === null || event.pointerId !== current.pointerId) return
    end()
    if (current.active && current.target !== null && current.target !== current.id) {
      options.onDrop(current.id, current.target)
    }
  }

  // While a finger drags, the page must not scroll along.
  function onTouchMove(event: TouchEvent): void {
    if (drag.value?.active) event.preventDefault()
  }

  return { drag, onPointerDown, onPointerMove, onPointerUp, onTouchMove, cancel: end }
}
