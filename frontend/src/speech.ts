// Speech output for answers. An engine speaks one piece of text at a time; the queue and the
// settings are in useSpeech. The browser's own voices come first; the Echo (through AIfred,
// see announce.py) and a TTS-Suite service (see speech_service.py) join when Agent-Orc's config has
// them.
import { ref } from 'vue'
import { api } from './api'
import { FrameReader } from './audioFrames'
import { i18n } from './i18n'
import { speechChunks } from './speechText'

export interface VoiceChoice {
  id: string
  label: string
}

export interface SpeechOptions {
  /** What was chosen with the engine: a voice, a room. */
  voice: string
  /** Speed and pitch the user set as overrides; null: the engine's own (the browser's voices: 1). */
  rate: number | null
  pitch: number | null
  /** Language of the text, as the interface language ("de", "en"). */
  lang: string
}

/** A piece of text given to an engine that works ahead (see `SpeechEngine.begin`). */
export interface SpeechJob {
  /** All its audio is here and queued: the next piece may be sent. */
  received: Promise<void>
  /** Its audio has been played to the end. */
  ended: Promise<void>
}

export interface SpeechEngine {
  id: string
  label: string
  /** Translation key of what is chosen with it: "Voice", "Room". */
  choiceLabel: string
  /** The most text an answer may have for this engine (cut at a sentence beforehand). */
  maxChars: number
  /** Whether the speed and pitch fields of the speech settings apply to it: the browser's voices and the TTS
   * service take them (the service as overrides of its own), the Echo has its own. */
  usesTempo: boolean
  /** The pieces of text the engine is given, one call each. */
  split: (text: string) => string[]
  /** Whether this device can speak with it. */
  available: () => boolean
  /** It has settings of its own, in a window of their own (the engines of a TTS service). */
  hasSettings?: boolean
  /** What can be chosen (voices of a language, rooms). */
  voices: (lang: string) => Promise<VoiceChoice[]>
  /** Speaks one piece of text; ends when it was spoken or cancelled. */
  speak: (text: string, options: SpeechOptions) => Promise<void>
  /**
   * An engine that makes the next piece while the one before is still being played has this too: it
   * sends the text at once and queues its audio behind what was begun before. The caller begins the
   * next piece when `received` of the one before is there, and waits for `ended` to know it was spoken.
   * Both end on `cancel` as well.
   */
  begin?: (text: string, options: SpeechOptions) => SpeechJob
  /**
   * An engine that takes all the answers as one announcement (the pauses and the tones around it
   * are its own business) has this instead of being given piece after piece; `speaker` is the
   * agent they are from.
   */
  speakAll?: (texts: string[], options: SpeechOptions, speaker: string) => Promise<void>
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
  usesTempo: true,
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
    utterance.rate = options.rate ?? 1
    utterance.pitch = options.pitch ?? 1
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

/** The Echo: AIfred speaks and queues; what is said cannot be stopped or paused from here. */
function echo(label: string, maxChars: number): SpeechEngine {
  const speakAll = (texts: string[], options: SpeechOptions, speaker: string): Promise<void> =>
    api.announceTexts(options.voice || ALL_ROOMS, texts, speaker)
  return {
    id: 'echo',
    usesTempo: false,
    label,
    choiceLabel: 'answers.room',
    maxChars,
    split: (text) => [text.replace(/\s*\n\s*/g, ' ')],
    available: () => true,
    async voices() {
      const { rooms } = await api.announce()
      const everyRoom = { id: ALL_ROOMS, label: i18n.global.t('answers.allRooms') }
      return [everyRoom, ...rooms.map((room) => ({ id: room, label: room }))]
    },
    speak: (text, options) => speakAll([text], options, ''),
    speakAll,
    cancel: () => undefined,
    pause: () => undefined,
    resume: () => undefined,
  }
}

/** What the service says when it fails after a reading has begun: `{error, detail}`. */
function frameError(body: Uint8Array): Error {
  const answer = JSON.parse(new TextDecoder().decode(body)) as { error: string; detail: string }
  return new Error(`${answer.error}: ${answer.detail}`)
}

/**
 * A TTS-Suite service: it chooses the engine, cleans and cuts the text and answers with audio as
 * it exists. The pieces are decoded and queued one after the other, so the first one starts while
 * the rest is still being made.
 */
function ttsSuite(label: string): SpeechEngine {
  let context: AudioContext | undefined
  // Every request that is running, so that a cancel ends all of them at once.
  const aborts = new Set<AbortController>()
  let playing = new Set<AudioBufferSourceNode>()
  // When the audio queued so far ends, on the clock of the context: the next piece starts there.
  let queuedUntil = 0

  function cancel(): void {
    for (const abort of aborts) abort.abort()
    aborts.clear()
    for (const source of playing) source.stop()
    playing = new Set()
    queuedUntil = 0
    void context?.resume()
  }

  /** Sends the text now; its audio is decoded and queued as it arrives, behind the audio before it. */
  function begin(text: string, options: SpeechOptions): SpeechJob {
    const controller = new AbortController()
    aborts.add(controller)
    const audio = (context ??= new AudioContext())
    let lastEnded: Promise<void> = Promise.resolve()
    const received = (async (): Promise<void> => {
      try {
        await audio.resume()
        const response = await api.ttsSpeak(text, options.lang, options.rate, options.pitch, controller.signal)
        const reader = (response.body as ReadableStream<Uint8Array>).getReader()
        const frames = new FrameReader()
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          for (const { header, body } of frames.push(value)) {
            if (header.kind === 'error') throw frameError(body)
            if (header.kind === 'audio' && (header.pause_ms ?? 0) > 0) {
              queuedUntil = Math.max(queuedUntil, audio.currentTime) + (header.pause_ms as number) / 1000
              continue
            }
            if (header.kind !== 'audio' || header.keepalive || body.length === 0) continue
            const buffer = await audio.decodeAudioData(body.buffer as ArrayBuffer)
            const source = audio.createBufferSource()
            source.buffer = buffer
            source.connect(audio.destination)
            queuedUntil = Math.max(queuedUntil, audio.currentTime)
            source.start(queuedUntil)
            queuedUntil += buffer.duration
            playing.add(source)
            lastEnded = new Promise((resolve) => {
              source.onended = () => resolve()
            })
          }
        }
        if (frames.incomplete) throw new Error('the speech service ended in the middle of a piece')
      } catch (error) {
        // Cancelling ends the request, which is no failure.
        if (!controller.signal.aborted) throw error
      } finally {
        aborts.delete(controller)
      }
    })()
    const ended = received.then(() => lastEnded)
    return { received, ended }
  }

  async function speak(text: string, options: SpeechOptions): Promise<void> {
    cancel()
    await begin(text, options).ended
  }

  return {
    id: 'tts-suite',
    usesTempo: true,
    label,
    choiceLabel: 'answers.voice',
    // The service cuts the text by what its engine takes and cleans it.
    maxChars: Number.POSITIVE_INFINITY,
    split: (text) => [text],
    available: () => true,
    // Which engines speak and with which voice is set in the engine's window of its own.
    hasSettings: true,
    voices: () => Promise.resolve([]),
    speak,
    begin,
    cancel,
    pause: () => void context?.suspend(),
    resume: () => void context?.resume(),
  }
}

/** The engines this device offers. */
const browserEngines = [browserSpeech].filter((engine) => engine.available())
export const speechEngines = ref<SpeechEngine[]>(browserEngines)

let serverEngines: Promise<void> | undefined

/** Adds the engines Agent-Orc's server offers (the Echo and a TTS-Suite service, if configured);
 * asked once. A service that does not answer is left out for now and asked again next time. */
export function loadServerEngines(): Promise<void> {
  serverEngines ??= Promise.allSettled([api.announce(), api.tts()]).then(([echoState, ttsState]) => {
    const found: SpeechEngine[] = []
    if (echoState.status === 'fulfilled' && echoState.value.configured) {
      found.push(echo(echoState.value.label, echoState.value.max_chars))
    }
    if (ttsState.status === 'fulfilled' && ttsState.value.configured) {
      found.push(ttsSuite(ttsState.value.label))
    }
    speechEngines.value = [...browserEngines, ...found]
    if (echoState.status === 'rejected' || ttsState.status === 'rejected') serverEngines = undefined
  })
  return serverEngines
}

export function speechEngine(id: string): SpeechEngine {
  const engine = speechEngines.value.find((candidate) => candidate.id === id)
  if (engine === undefined) throw new Error(`speech output "${id}" is not available`)
  return engine
}
