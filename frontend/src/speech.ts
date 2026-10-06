// Speech output for answers. An engine speaks one piece of text at a time; the queue and the
// settings are in useSpeech. The browser's own voices come first; the Echo Dot (through AIfred,
// see announce.py) joins when Agent-Orc's config has it. A speech service on the server would be
// one more engine in this list.
import { ref } from 'vue'
import { api } from './api'
import { i18n } from './i18n'
import { speechChunks } from './speechText'

export interface VoiceChoice {
  id: string
  label: string
}

export interface SpeechOptions {
  /** What was chosen with the engine: a voice, a room. */
  voice: string
  rate: number
  /** Language of the text, as the interface language ("de", "en"). */
  lang: string
}

export interface SpeechEngine {
  id: string
  label: string
  /** Translation key of what is chosen with it: "Voice", "Room". */
  choiceLabel: string
  /** The most text an answer may have for this engine (cut at a sentence beforehand). */
  maxChars: number
  /** The pieces of text the engine is given, one call each. */
  split: (text: string) => string[]
  /** Whether this device can speak with it. */
  available: () => boolean
  /** What can be chosen (voices of a language, rooms). */
  voices: (lang: string) => Promise<VoiceChoice[]>
  /** Speaks one piece of text; ends when it was spoken or cancelled. */
  speak: (text: string, options: SpeechOptions) => Promise<void>
  cancel: () => void
  pause: () => void
  resume: () => void
}

// Some browsers load their voices late and never announce it.
const VOICES_WAIT_MS = 1500
const synthesis: SpeechSynthesis | undefined = window.speechSynthesis

function browserVoices(): Promise<SpeechSynthesisVoice[]> {
  if (synthesis === undefined) return Promise.resolve([])
  const now = synthesis.getVoices()
  if (now.length > 0) return Promise.resolve(now)
  return new Promise((resolve) => {
    const done = () => resolve(synthesis.getVoices())
    synthesis.addEventListener('voiceschanged', done, { once: true })
    window.setTimeout(done, VOICES_WAIT_MS)
  })
}

const browserSpeech: SpeechEngine = {
  id: 'browser',
  label: 'Browser',
  choiceLabel: 'answers.voice',
  // Any length, but spoken in short pieces: browsers cut off a long utterance.
  maxChars: Number.POSITIVE_INFINITY,
  split: (text) => speechChunks(text),
  available: () => synthesis !== undefined,
  async voices(lang) {
    const voices = await browserVoices()
    return voices
      .filter((voice) => voice.lang.toLowerCase().startsWith(lang))
      .map((voice) => ({ id: voice.voiceURI, label: voice.name }))
  },
  async speak(text, options) {
    if (synthesis === undefined) return
    const voices = await browserVoices()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = options.lang
    utterance.rate = options.rate
    const chosen = voices.find((voice) => voice.voiceURI === options.voice)
    if (chosen) utterance.voice = chosen
    return new Promise<void>((resolve, reject) => {
      utterance.onend = () => resolve()
      utterance.onerror = (event) => {
        // Stopping the speech ends the piece with these, which is no failure.
        if (event.error === 'canceled' || event.error === 'interrupted') resolve()
        else reject(new Error(event.error))
      }
      synthesis.speak(utterance)
    })
  },
  cancel: () => synthesis?.cancel(),
  pause: () => synthesis?.pause(),
  resume: () => synthesis?.resume(),
}

/** Every room with an Echo connected. */
const ALL_ROOMS = '*'

/** The Echo Dot: AIfred speaks and queues; what is said cannot be stopped or paused from here. */
function echoDot(maxChars: number): SpeechEngine {
  return {
    id: 'echo',
    label: 'Echo Dot',
    choiceLabel: 'answers.room',
    maxChars,
    // One announcement of its own (with the signal tones around it) for each answer.
    split: (text) => [text.replace(/\s*\n\s*/g, ' ')],
    available: () => true,
    async voices() {
      const { rooms } = await api.announce()
      const everyRoom = { id: ALL_ROOMS, label: i18n.global.t('answers.allRooms') }
      return [everyRoom, ...rooms.map((room) => ({ id: room, label: room }))]
    },
    speak: (text, options) => api.announceText(options.voice || ALL_ROOMS, text),
    cancel: () => undefined,
    pause: () => undefined,
    resume: () => undefined,
  }
}

/** The engines this device offers. */
export const speechEngines = ref<SpeechEngine[]>([browserSpeech].filter((engine) => engine.available()))

let serverEngines: Promise<void> | undefined

/** Adds the engines Agent-Orc's server offers (the Echo Dot, if configured); asked once. */
export function loadServerEngines(): Promise<void> {
  serverEngines ??= api.announce().then(
    (state) => {
      if (state.configured) speechEngines.value = [...speechEngines.value, echoDot(state.max_chars)]
    },
    (error: unknown) => {
      // AIfred may be down right now: ask again next time.
      serverEngines = undefined
      throw error
    },
  )
  return serverEngines
}

export function speechEngine(id: string): SpeechEngine {
  const engine = speechEngines.value.find((candidate) => candidate.id === id)
  if (engine === undefined) throw new Error(`speech output "${id}" is not available`)
  return engine
}
