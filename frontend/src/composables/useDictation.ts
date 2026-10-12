import { computed, onScopeDispose, ref, type UnwrapNestedRefs } from 'vue'
import { api } from '../api'
import { useSettings } from './useSettings'
import { START_BEEP, STOP_BEEP, playBeep } from '../sounds'

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
}
type SpeechResults = ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>
type SpeechRecognitionClass = new () => SpeechRecognitionLike

const speechWindow = window as unknown as {
  SpeechRecognition?: SpeechRecognitionClass
  webkitSpeechRecognition?: SpeechRecognitionClass
}
// Chrome has it (sending the audio to Google), Firefox does not.
const BrowserRecognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition

export type DictationState = 'idle' | 'recording' | 'transcribing' | 'listening'

/**
 * Speech input. With an STT-Suite service the browser records and the service transcribes on the
 * device the user picked; the browser's own recognition is then only offered after the service
 * failed, as a separate button pressed deliberately. Without an STT-Suite service the microphone
 * uses the browser's recognition directly.
 */

export function useDictation(
  onText: (text: string) => void,
  onError: (error: unknown) => void,
) {
  const state = ref<DictationState>('idle')
  // Where the STT-Suite transcribes: one setting of this device (in the settings menu), the same for every agent.
  const { dictationDevice: device } = useSettings()
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
  const sttFailed = ref(false)
  // Kept when the STT-Suite failed, so the dictation is not lost: it can be sent again, e.g. on the CPU.
  const failedAudio = ref<Blob | null>(null)
  let recorder: MediaRecorder | null = null
  let recognition: SpeechRecognitionLike | null = null

  const hasBrowserRecognition = BrowserRecognition !== undefined
  const microphone = computed(
    () => stt.value === true || (stt.value === false && hasBrowserRecognition),
  )
  const browserFallback = computed(
    () => stt.value === true && sttFailed.value && hasBrowserRecognition,
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
      void transcribe(new Blob(chunks, { type: mimeType }))
    }
    recorder.start()
    playBeep(START_BEEP)
    state.value = 'recording'
  }

  async function transcribe(audio: Blob): Promise<void> {
    state.value = 'transcribing'
    failedAudio.value = null
    try {
      const { text } = await api.dictate(audio, device.value)
      sttFailed.value = false
      if (text) onText(text)
    } catch (error) {
      sttFailed.value = true
      failedAudio.value = audio
      onError(error)
    } finally {
      state.value = 'idle'
      void refreshService()
    }
  }

  function startListening(): void {
    if (BrowserRecognition === undefined) return
    recognition = new BrowserRecognition()
    recognition.lang = language.value
    recognition.continuous = true
    recognition.interimResults = false
    recognition.onresult = (event) => {
      for (let index = event.resultIndex; index < event.results.length; index++) {
        const result = event.results[index]
        if (result.isFinal) onText(result[0].transcript.trim())
      }
    }
    recognition.onerror = (event) => onError(new Error(event.error))
    // Also when the browser stops by itself after a silence.
    recognition.onend = () => {
      playBeep(STOP_BEEP)
      state.value = 'idle'
    }
    recognition.start()
    playBeep(START_BEEP)
    state.value = 'listening'
  }

  /** Send the recording that failed once more, with the device chosen now. */
  function retry(): void {
    if (failedAudio.value !== null && state.value === 'idle') void transcribe(failedAudio.value)
  }

  /** Browser recognition: start, or stop until pressed again. */
  function toggleBrowser(): void {
    if (state.value === 'listening') recognition?.stop()
    else if (state.value === 'idle') startListening()
  }

  /** Microphone button: the STT-Suite when there is a service, else the browser's recognition. */
  function toggleMicrophone(): void {
    if (stt.value === false) toggleBrowser()
    else if (state.value === 'recording') {
      playBeep(STOP_BEEP)
      recorder?.stop()
    } else if (state.value === 'idle') startRecording().catch(onError)
  }

  return {
    state,
    device,
    gpuLoaded,
    stt,
    microphone,
    browserFallback,
    failedAudio,
    retry,
    toggleMicrophone,
    toggleBrowser,
  }
}

/** What the dictation buttons need: the result of useDictation, wrapped in reactive(). */
export type Dictation = UnwrapNestedRefs<ReturnType<typeof useDictation>>
