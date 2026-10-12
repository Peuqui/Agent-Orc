import { type Ref, computed, ref, watch } from 'vue'
import { sharedSetting } from './useSharedSettings'

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
// Font sizes in pixels, for the terminal and for the views (answers, notes, conversations,
// files, consumption) alike, so both are set in the same unit and within the same bounds.
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
  // What arrived from another document is not stored again: every document would otherwise
  // write back the older value it heard last, and the documents keep correcting each other
  // (two quick steps of the font size made it jump between two sizes for good). The watcher
  // runs at once, so the flag covers exactly that change.
  let fromOtherDocument = false
  watch(
    value,
    (current) => {
      if (!fromOtherDocument) localStorage.setItem(key, String(current))
    },
    { flush: 'sync' },
  )
  updatersByKey.set(key, (text) => {
    fromOtherDocument = true
    value.value = parse(text)
    fromOtherDocument = false
  })
  return value
}

/** Lines one wheel notch or swipe step scrolls in the terminal. */
const scrollLines = setting('agent-orc-scroll-lines', DEFAULT_SCROLL_LINES, Number)
/** Line spacing of the terminal, as a multiple of the font size. */
const lineHeight = setting('agent-orc-line-height', DEFAULT_LINE_HEIGHT, Number)
/** Font size of every terminal of this device. */
const fontSize = setting('agent-orc-font-size', DEFAULT_FONT_SIZE, Number)
/** Font size of every view of this device: the base size its texts are scaled from (useViewZoom). */
const viewFontSize = setting('agent-orc-view-font-size', DEFAULT_FONT_SIZE, Number)
const terminalFont = setting<TerminalFont>(
  'agent-orc-terminal-font',
  'jetbrains',
  (stored) => stored as TerminalFont,
)

// What is the same on every device lives on the server (shared_settings.py, useSharedSettings.ts); what depends on
// the device itself (fonts, scrolling, the browser's voices, the columns) is kept here, in the browser.

/** A dictation goes to the agent as soon as it is transcribed, without pressing send. */
const dictationSendsAtOnce = sharedSetting('dictation_sends_at_once')

/** Where Whisper transcribes the dictations, for every agent and device: the CPU unless the GPU was chosen on purpose. */
const dictationDevice = sharedSetting('dictation_device')

/** What a terminal shows: the terminal itself, or the agent's answers in short (AnswersFeed). */
export type TerminalView = 'terminal' | 'answers'
/** What this agent's terminal shows; each agent has its own. The answers are what it shows first, the terminal itself is one tap away. */
export function useTerminalView(sessionId: string): Ref<TerminalView> {
  return setting<TerminalView>(`agent-orc-terminal-view:${sessionId}`, 'answers', (stored) => stored as TerminalView)
}
const answersAllKey = (sessionId: string) => `agent-orc-answers-all:${sessionId}`

/** An agent's answers show every text it wrote, not only the last one of each request; each agent has its own choice. */
export function useAnswersAll(sessionId: string): Ref<boolean> {
  return setting(answersAllKey(sessionId), false, (stored) => stored === 'true')
}

/** The choice of an agent, read once (for a page that is not showing its answers). */
export function readAnswersAll(sessionId: string): boolean {
  return localStorage.getItem(answersAllKey(sessionId)) === 'true'
}

/** What reads answers aloud: the engine (speech.ts), its voice, and its speed and pitch as overrides (none: the engine's own). */
const speechEngine = sharedSetting('speech_engine')
// What is chosen with an engine (a room of the Echo, a voice of the TTS service) is kept on the server, one for each; the
// voices of the browser are the device's own and stay in the browser.
const BROWSER_ENGINE = 'browser'
const browserVoice = setting(`agent-orc-speech-voice:${BROWSER_ENGINE}`, '', String)
const speechVoices = sharedSetting('speech_voices')
const voiceRefs = new Map<string, Ref<string>>()
export function useSpeechVoice(engineId: string): Ref<string> {
  if (engineId === BROWSER_ENGINE) return browserVoice
  let voice = voiceRefs.get(engineId)
  if (voice === undefined) {
    voice = computed({
      get: () => speechVoices.value[engineId] ?? '',
      set: (chosen: string) => {
        speechVoices.value = { ...speechVoices.value, [engineId]: chosen }
      },
    })
    voiceRefs.set(engineId, voice)
  }
  return voice
}
const speechRate = sharedSetting('speech_rate')
const speechPitch = sharedSetting('speech_pitch')
/** The agent's name is spoken before its answer, so one hears who is speaking. */
const speechAnnounceName = sharedSetting('speech_announce_name')
/** The workspace reads new answers of its columns aloud by itself, as they arrive. */
const speechAutoRead = setting('agent-orc-speech-auto-read', false, (stored) => stored === 'true')
/** Without a paragraph for listening, an answer is read up to this many characters. */
const speechMaxChars = sharedSetting('speech_max_chars')

/** Bumped when the extra keys were arranged anew: every open terminal fetches them again (the
 * arrangement itself is kept on the server, for every device). */
const extraKeysVersion = setting('agent-orc-extra-keys-version', 0, Number)

/** All rows of extra keys; folded, only the first (the config orders them). */
const extraKeysUnfolded = setting('agent-orc-extra-keys-unfolded', false, (stored) => stored === 'true')

/** One pixel larger (1) or smaller (-1), within the bounds. */
function stepWithinBounds(size: Ref<number>, delta: number): void {
  size.value = Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, size.value + delta))
}

/** The terminal's font size; from the settings or a terminal. */
function stepFontSize(delta: number): void {
  stepWithinBounds(fontSize, delta)
}

/** The views' font size; from the settings or the editor. */
function stepViewFontSize(delta: number): void {
  stepWithinBounds(viewFontSize, delta)
}

export function useSettings() {
  return {
    scrollLines,
    lineHeight,
    fontSize,
    stepFontSize,
    viewFontSize,
    stepViewFontSize,
    terminalFont,
    dictationSendsAtOnce,
    dictationDevice,
    extraKeysUnfolded,
    extraKeysVersion,
    speechEngine,
    speechRate,
    speechPitch,
    speechMaxChars,
    speechAnnounceName,
    speechAutoRead,
  }
}
