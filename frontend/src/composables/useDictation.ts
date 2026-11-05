import { computed, onScopeDispose, ref, type UnwrapNestedRefs } from 'vue'
import { api } from '../api'
import { transcribeForAgent } from '../dictationHost'
import { useSettings, type DictationEngine } from './useSettings'
import { loadSignals, playSignal } from '../sounds'

// Recording formats the STT-Suite is fed with (agent_orc.dictation.AUDIO_SUFFIXES),
// best first: Chrome records WebM, Firefox Ogg, Safari MP4.
const RECORDING_TYPES = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']

/** The parts of the Web Speech API used here; TypeScript's DOM types do not include it. */
interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: { resultIndex: number; results: SpeechResults }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}
type SpeechResults = ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>
type SpeechRecognitionClass = new () => SpeechRecognitionLike

const speechWindow = window as unknown as {
  SpeechRecognition?: SpeechRecognitionClass
  webkitSpeechRecognition?: SpeechRecognitionClass
}
// Chrome has it (sending the audio to Google), Firefox does not.
const BrowserRecognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition
export const hasBrowserRecognition = BrowserRecognition !== undefined

export type DictationState = 'idle' | 'recording' | 'transcribing' | 'listening'

/**
 * Speech input, through the engine chosen for this device in the settings menu. With the STT-Suite the
 * browser records and the service transcribes on the device the user picked; with the browser chosen, or
 * without an STT-Suite service, the browser's own recognition listens. Either way the microphone button
 * starts and ends a dictation, and its text comes as one piece at the end.
 */

export function useDictation(
  /** `interrupted`: the dictation ended by an error, so what came is maybe not all that was said: it is never
   * sent without the user seeing it. */
  onText: (text: string, interrupted: boolean) => void,
  onError: (error: unknown) => void,
  /** The agent whose field is dictated into: transcribed on the page at the top of the tab (dictationHost.ts). */
  sessionId?: string,
) {
  const state = ref<DictationState>('idle')
  // Recording or listening: what is said is being taken in (it can still be cancelled).
  const active = computed(() => state.value === 'recording' || state.value === 'listening')
  // What recognises (this device's choice) and where the STT-Suite transcribes (the same on every device).
  const { dictationDevice: device, dictationEngine, dictationSounds } = useSettings()
  // Unknown until the server's settings have arrived.
  const stt = ref<boolean | null>(null)
  // Whether the service has a model on the GPU: asked at the start and after every dictation, which is
  // what loads it (with "auto" the service decides where a dictation runs) or finds it gone. The idle
  // GPU worker ends itself after a time the service reports, so it is asked again when that is over: the
  // answer says whether someone else used the GPU meanwhile (the time starts anew) or the model is gone.
  const gpuLoaded = ref(false)
  let unloadCheck: ReturnType<typeof setTimeout> | undefined
  onScopeDispose(() => clearTimeout(unloadCheck))
  const language = ref('')
  // Kept when the STT-Suite failed, so the dictation is not lost: it can be sent again, e.g. on the CPU.
  const failedAudio = ref<Blob | null>(null)
  let recorder: MediaRecorder | null = null
  let recognition: SpeechRecognitionLike | null = null
  // Only the microphone button (or an error) ends listening: the browser stops by itself after a silence and is
  // started again then, so a pause to think does not end the dictation. What was heard comes as one text at the end.
  let ending = false
  let interrupted = false
  // Set by cancel(): what was recorded or heard is thrown away, not transcribed.
  let cancelled = false
  let heard: string[] = []
  onScopeDispose(() => {
    ending = true
    heard = []
    recognition?.abort()
  })

  // What the microphone uses; null until the server's settings have arrived.
  const engine = computed<DictationEngine | null>(() => {
    if (stt.value === null) return null
    return stt.value ? dictationEngine.value : 'browser'
  })
  const microphone = computed(
    () => engine.value === 'stt-suite' || (engine.value === 'browser' && hasBrowserRecognition),
  )

  function refreshService(): Promise<void> {
    return api
      .dictationSettings()
      .then((settings) => {
        stt.value = settings.stt
        language.value = settings.language
        gpuLoaded.value = settings.service?.gpu_loaded ?? false
        clearTimeout(unloadCheck)
        const remaining = settings.service?.gpu_ttl_remaining_seconds
        if (gpuLoaded.value && remaining != null) {
          unloadCheck = setTimeout(() => void refreshService(), (remaining + 1) * 1000)
        }
      })
      .catch(onError)
  }
  void refreshService()
  // Ahead of the first dictation, so its tone sounds at once.
  loadSignals(dictationSounds.value).catch(onError)

  async function startRecording(): Promise<void> {
    const mimeType = RECORDING_TYPES.find((type) => MediaRecorder.isTypeSupported(type))
    if (mimeType === undefined) throw new Error('No supported audio recording format')
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const chunks: Blob[] = []
    recorder = new MediaRecorder(stream, { mimeType })
    recorder.ondataavailable = (event) => chunks.push(event.data)
    recorder.onstop = () => {
      // Releases the microphone, so the browser's recording indicator goes away.
      for (const track of stream.getTracks()) track.stop()
      if (cancelled) state.value = 'idle'
      else void transcribe(new Blob(chunks, { type: mimeType }))
    }
    cancelled = false
    recorder.start()
    playSignal('start', dictationSounds.value).catch(onError)
    state.value = 'recording'
  }

  async function transcribe(audio: Blob): Promise<void> {
    state.value = 'transcribing'
    failedAudio.value = null
    try {
      const text = sessionId === undefined ? (await api.dictate(audio, device.value)).text : await transcribeForAgent(sessionId, audio, device.value)
      if (text) onText(text, false)
    } catch (error) {
      failedAudio.value = audio
      onError(error)
    } finally {
      state.value = 'idle'
      void refreshService()
    }
  }

  function startListening(): void {
    if (BrowserRecognition === undefined) return
    const listener = new BrowserRecognition()
    listener.lang = language.value
    listener.continuous = true
    listener.interimResults = false
    listener.onresult = (event) => {
      for (let index = event.resultIndex; index < event.results.length; index++) {
        const result = event.results[index]
        if (result.isFinal) heard.push(result[0].transcript.trim())
      }
    }
    // "no-speech" is a silence before anything was said: it ends like any other silence. "aborted" follows a
    // cancel (abort()).
    listener.onerror = (event) => {
      if (event.error === 'no-speech' || cancelled) return
      ending = true
      interrupted = true
      onError(new Error(event.error))
    }
    listener.onend = () => {
      if (!ending) {
        try {
          listener.start()
          return
        } catch (error) {
          // Some browsers start only from a tap (Safari), which the restart is not: the dictation ends here.
          interrupted = true
          onError(error)
        }
      }
      recognition = null
      state.value = 'idle'
      const text = heard.filter(Boolean).join(' ')
      heard = []
      if (cancelled) return
      playSignal('stop', dictationSounds.value).catch(onError)
      if (text) onText(text, interrupted)
    }
    recognition = listener
    ending = false
    interrupted = false
    cancelled = false
    listener.start()
    playSignal('start', dictationSounds.value).catch(onError)
    state.value = 'listening'
  }

  /** Send the recording that failed once more, with the device chosen now. */
  function retry(): void {
    if (failedAudio.value !== null && state.value === 'idle') void transcribe(failedAudio.value)
  }

  /** Microphone button: the engine chosen (the browser's recognition without a service). */
  function toggleMicrophone(): void {
    if (state.value === 'listening') {
      ending = true
      recognition?.stop()
    } else if (state.value === 'idle' && engine.value === 'browser') startListening()
    else if (state.value === 'recording') {
      playSignal('stop', dictationSounds.value).catch(onError)
      recorder?.stop()
    } else if (state.value === 'idle') startRecording().catch(onError)
  }

  /** Throws a running dictation away: nothing is transcribed. As in Mundwerk, only while it records or listens. */
  function cancel(): void {
    if (!active.value) return
    cancelled = true
    ending = true
    playSignal('cancel', dictationSounds.value).catch(onError)
    if (state.value === 'recording') recorder?.stop()
    else recognition?.abort()
  }

  // Escape cancels, but only a running dictation: otherwise it goes where it went (in the terminal it interrupts
  // the agent). Caught before the page sees it, so it does not reach the terminal either.
  function cancelOnEscape(event: KeyboardEvent): void {
    if (event.key !== 'Escape' || !active.value) return
    event.preventDefault()
    event.stopPropagation()
    cancel()
  }
  window.addEventListener('keydown', cancelOnEscape, { capture: true })
  onScopeDispose(() => window.removeEventListener('keydown', cancelOnEscape, { capture: true }))

  return {
    state,
    active,
    device,
    gpuLoaded,
    engine,
    microphone,
    failedAudio,
    retry,
    toggleMicrophone,
    cancel,
  }
}

/** What the dictation buttons need: the result of useDictation, wrapped in reactive(). */
export type Dictation = UnwrapNestedRefs<ReturnType<typeof useDictation>>
