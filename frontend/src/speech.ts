// Speech output for answers. An engine speaks one piece of text at a time; the queue and the
// settings are in useSpeech. The browser's own voices come first; more engines (a speech
// service on the server such as Piper, or the Echo Dot through AIfred) are added to the list.

export interface VoiceChoice {
  id: string
  label: string
}

export interface SpeechOptions {
  voice: string
  rate: number
  /** Language of the text, as the interface language ("de", "en"). */
  lang: string
}

export interface SpeechEngine {
  id: string
  label: string
  /** Whether this device can speak with it. */
  available: () => boolean
  /** The voices on offer for a language. */
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

/** The engines this device offers. */
export const speechEngines: SpeechEngine[] = [browserSpeech].filter((engine) => engine.available())

export function speechEngine(id: string): SpeechEngine {
  const engine = speechEngines.find((candidate) => candidate.id === id) ?? speechEngines[0]
  if (engine === undefined) throw new Error('no speech output on this device')
  return engine
}
