import { type Ref, ref, watch } from 'vue'

// Settings of this device (a phone scrolls differently than a mouse wheel), kept in the
// browser. The workspace's iframes share the storage; the storage event tells them about a
// change made in another document.
const SCROLL_LINES_KEY = 'agent-orc-scroll-lines'
const LINE_HEIGHT_KEY = 'agent-orc-line-height'
export const DEFAULT_SCROLL_LINES = 3
export const MIN_SCROLL_LINES = 1
export const MAX_SCROLL_LINES = 20
// xterm.js sets lines without any spacing (1.0), which reads cramped.
export const DEFAULT_LINE_HEIGHT = 1.2
export const MIN_LINE_HEIGHT = 1
export const MAX_LINE_HEIGHT = 1.6
export const LINE_HEIGHT_STEP = 0.05

/** Lines one wheel notch or swipe step scrolls in the terminal. */
const scrollLines = ref(Number(localStorage.getItem(SCROLL_LINES_KEY)) || DEFAULT_SCROLL_LINES)

/** Line spacing of the terminal, as a multiple of the font size. */
const lineHeight = ref(Number(localStorage.getItem(LINE_HEIGHT_KEY)) || DEFAULT_LINE_HEIGHT)

watch(scrollLines, (lines) => localStorage.setItem(SCROLL_LINES_KEY, String(lines)))
watch(lineHeight, (height) => localStorage.setItem(LINE_HEIGHT_KEY, String(height)))

const SETTINGS_BY_KEY: Record<string, Ref<number>> = {
  [SCROLL_LINES_KEY]: scrollLines,
  [LINE_HEIGHT_KEY]: lineHeight,
}

window.addEventListener('storage', (event) => {
  const setting = event.key === null ? undefined : SETTINGS_BY_KEY[event.key]
  if (setting && event.newValue) setting.value = Number(event.newValue)
})

export function useSettings() {
  return { scrollLines, lineHeight }
}
