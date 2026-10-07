import { computed, ref, type UnwrapNestedRefs } from 'vue'
import { api, type DictationDevice } from '../api'
import { START_BEEP, STOP_BEEP, playBeep } from '../sounds'

// Recording formats the Whisper service is fed with (agent_orc.dictation.AUDIO_SUFFIXES),
// best first: Chrome records WebM, Firefox Ogg, Safari MP4.
const RECORDING_TYPES = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']
// The device is remembered per agent: the CPU unless the GPU was chosen on purpose there.
const DEVICE_KEY = 'agent-orc-dictation-device:'

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
 * Speech input. With a Whisper service the browser records and Whisper transcribes on the
 * device the user picked; the browser's own recognition is then only offered after Whisper
 * failed, as a separate button pressed deliberately. Without a Whisper service the microphone
 * uses the browser's recognition directly.
 */

export function useDictation(
  sessionId: string,
  onText: (text: string) => void,
  onError: (error: unknown) => void,
) {
  const state = ref<DictationState>('idle')
  const device = ref<DictationDevice>(localStorage.getItem(DEVICE_KEY + sessionId) === 'cuda' ? 'cuda' : 'cpu')
  // Unknown until the server's settings have arrived.
  const whisper = ref<boolean | null>(null)
  const language = ref('')
  const whisperFailed = ref(false)
  // Kept when Whisper failed, so the dictation is not lost: it can be sent again, e.g. on the CPU.
  const failedAudio = ref<Blob | null>(null)
  let recorder: MediaRecorder | null = null
  let recognition: SpeechRecognitionLike | null = null

  const hasBrowserRecognition = BrowserRecognition !== undefined
  const microphone = computed(
    () => whisper.value === true || (whisper.value === false && hasBrowserRecognition),
  )
  const browserFallback = computed(
    () => whisper.value === true && whisperFailed.value && hasBrowserRecognition,
  )

  api
    .dictationSettings()
    .then((settings) => {
      whisper.value = settings.whisper
      language.value = settings.language
    })
    .catch(onError)

  function toggleDevice(): void {
    device.value = device.value === 'cuda' ? 'cpu' : 'cuda'
    localStorage.setItem(DEVICE_KEY + sessionId, device.value)
  }

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
      whisperFailed.value = false
      if (text) onText(text)
    } catch (error) {
      whisperFailed.value = true
      failedAudio.value = audio
      onError(error)
    } finally {
      state.value = 'idle'
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

  /** Microphone button: Whisper when there is a service, else the browser's recognition. */
  function toggleMicrophone(): void {
    if (whisper.value === false) toggleBrowser()
    else if (state.value === 'recording') {
      playBeep(STOP_BEEP)
      recorder?.stop()
    } else if (state.value === 'idle') startRecording().catch(onError)
  }

  return {
    state,
    device,
    whisper,
    microphone,
    browserFallback,
    failedAudio,
    retry,
    toggleDevice,
    toggleMicrophone,
    toggleBrowser,
  }
}

/** What the dictation buttons need: the result of useDictation, wrapped in reactive(). */
export type Dictation = UnwrapNestedRefs<ReturnType<typeof useDictation>>
