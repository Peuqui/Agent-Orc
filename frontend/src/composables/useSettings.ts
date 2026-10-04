import { type Ref, ref, watch } from 'vue'

// Settings of this device (a phone scrolls and reads differently than a desktop), kept in the
// browser. The workspace's iframes share the storage; the storage event tells them about a
// change made in another document.
export const DEFAULT_SCROLL_LINES = 3
export const MIN_SCROLL_LINES = 1
export const MAX_SCROLL_LINES = 20
// xterm.js sets lines without any spacing (1.0), which reads cramped.
export const DEFAULT_LINE_HEIGHT = 1.2
export const MIN_LINE_HEIGHT = 1
export const MAX_LINE_HEIGHT = 1.6
export const LINE_HEIGHT_STEP = 0.05
export const DEFAULT_FONT_SIZE = 14
export const MIN_FONT_SIZE = 8
export const MAX_FONT_SIZE = 28

// Noto Sans Symbols 2 follows each font for the symbols Claude Code draws (⏵ ⏺ ● ✻ ⎿), which
// the monospace fonts lack; also shipped with the app (OFL), as phones often have none.
const SYMBOLS = '"Noto Sans Symbols 2"'
/** Terminal fonts: monospace, as the agents draw tables and frames from characters. */
export const TERMINAL_FONTS = {
  // Shipped with the app (OFL), so every device shows the same font made for screens.
  jetbrains: `"JetBrains Mono Variable", ${SYMBOLS}, ui-monospace, monospace`,
  system: `ui-monospace, "Cascadia Mono", "DejaVu Sans Mono", ${SYMBOLS}, monospace`,
} as const
/** Loading these characters fetches every font part the terminal needs before it draws. */
export const FONT_SAMPLE = 'Aä⏵⏺●✻⎿⠋∑'
export type TerminalFont = keyof typeof TERMINAL_FONTS

const updatersByKey = new Map<string, (stored: string) => void>()

window.addEventListener('storage', (event) => {
  if (event.key !== null && event.newValue !== null) updatersByKey.get(event.key)?.(event.newValue)
})

/** A setting stored under key; parse turns the stored text back into its value. */
function setting<T>(key: string, initial: T, parse: (stored: string) => T): Ref<T> {
  const stored = localStorage.getItem(key)
  const value = ref(stored === null ? initial : parse(stored)) as Ref<T>
  watch(value, (current) => localStorage.setItem(key, String(current)))
  updatersByKey.set(key, (text) => (value.value = parse(text)))
  return value
}

/** Lines one wheel notch or swipe step scrolls in the terminal. */
const scrollLines = setting('agent-orc-scroll-lines', DEFAULT_SCROLL_LINES, Number)
/** Line spacing of the terminal, as a multiple of the font size. */
const lineHeight = setting('agent-orc-line-height', DEFAULT_LINE_HEIGHT, Number)
/** Font size of every terminal, unless A−/A+ set one larger or smaller. */
const fontSize = setting('agent-orc-font-size', DEFAULT_FONT_SIZE, Number)
const terminalFont = setting<TerminalFont>(
  'agent-orc-terminal-font',
  'jetbrains',
  (stored) => stored as TerminalFont,
)

/** Speech recognition engine of the Whisper service for dictation; empty: the service's default. */
const dictationEngine = setting('agent-orc-dictation-engine', '', String)

/** All rows of extra keys; folded, only the first (the config orders them). */
const extraKeysUnfolded = setting('agent-orc-extra-keys-unfolded', false, (stored) => stored === 'true')

/** One step larger (1) or smaller (-1), within the bounds; from the settings or a terminal. */
function stepFontSize(delta: number): void {
  fontSize.value = Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, fontSize.value + delta))
}

export function useSettings() {
  return {
    scrollLines,
    lineHeight,
    fontSize,
    stepFontSize,
    terminalFont,
    dictationEngine,
    extraKeysUnfolded,
  }
}
