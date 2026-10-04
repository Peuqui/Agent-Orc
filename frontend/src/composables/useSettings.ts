import { ref, watch } from 'vue'

// Settings of this device (a phone scrolls differently than a mouse wheel), kept in the
// browser. The workspace's iframes share the storage; the storage event tells them about a
// change made in another document.
const SCROLL_LINES_KEY = 'agent-orc-scroll-lines'
export const DEFAULT_SCROLL_LINES = 3
export const MIN_SCROLL_LINES = 1
export const MAX_SCROLL_LINES = 20

/** Lines one wheel notch or swipe step scrolls in the terminal. */
const scrollLines = ref(Number(localStorage.getItem(SCROLL_LINES_KEY)) || DEFAULT_SCROLL_LINES)

watch(scrollLines, (lines) => localStorage.setItem(SCROLL_LINES_KEY, String(lines)))

window.addEventListener('storage', (event) => {
  if (event.key === SCROLL_LINES_KEY && event.newValue) scrollLines.value = Number(event.newValue)
})

export function useSettings() {
  return { scrollLines }
}
