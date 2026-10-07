import { onBeforeUnmount } from 'vue'

// Enough of an element on screen to have been looked at: half of it, or this much of a tall one.
const MIN_VISIBLE_PX = 120
const VISIBLE_HALF = 0.5
const THRESHOLD_STEPS = 20

/**
 * Tells which of the elements marked `data-seen-id` have been looked at: mostly on screen for
 * `dwellMs` while the page is visible. `observe` takes the elements inside a container (again
 * after the container changed; observing an element twice does no harm).
 */
export function useSeenOnScreen(seen: (id: string) => void, dwellMs: number) {
  const timers = new Map<string, number>()

  function arm(id: string): void {
    window.clearTimeout(timers.get(id))
    timers.set(
      id,
      window.setTimeout(() => {
        // A page in the background is not looked at: ask again after another moment.
        if (document.visibilityState !== 'visible') return arm(id)
        timers.delete(id)
        seen(id)
      }, dwellMs),
    )
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const id = (entry.target as HTMLElement).dataset.seenId
        if (id === undefined) continue
        const needed = Math.min(entry.boundingClientRect.height * VISIBLE_HALF, MIN_VISIBLE_PX)
        if (entry.isIntersecting && entry.intersectionRect.height >= needed) {
          if (!timers.has(id)) arm(id)
        } else {
          window.clearTimeout(timers.get(id))
          timers.delete(id)
        }
      }
    },
    { threshold: Array.from({ length: THRESHOLD_STEPS + 1 }, (_unused, step) => step / THRESHOLD_STEPS) },
  )

  function observe(container: HTMLElement): void {
    container.querySelectorAll<HTMLElement>('[data-seen-id]').forEach((element) => observer.observe(element))
  }

  onBeforeUnmount(() => {
    observer.disconnect()
    timers.forEach((timer) => window.clearTimeout(timer))
  })

  return { observe }
}
