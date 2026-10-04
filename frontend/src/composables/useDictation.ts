import { ref } from 'vue'
import { api, type DictationDevice } from '../api'

// Recording formats the Whisper service is fed with (agent_orc.dictation.AUDIO_SUFFIXES),
// best first: Chrome records WebM, Firefox Ogg, Safari MP4.
const RECORDING_TYPES = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']
const DEVICE_KEY = 'agent-orc-dictation-device'

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
 * Speech input: recorded in the browser and transcribed by the local Whisper service on the
 * device the user picked. Only when Whisper fails is the browser's own recognition offered,
 * as a separate button the user presses deliberately.
 */
export function useDictation(onText: (text: string) => void, onError: (error: unknown) => void) {
  const state = ref<DictationState>('idle')
  const device = ref<DictationDevice>(localStorage.getItem(DEVICE_KEY) === 'cpu' ? 'cpu' : 'cuda')
  const browserFallback = ref(false)
  let recorder: MediaRecorder | null = null
  let recognition: SpeechRecognitionLike | null = null

  function toggleDevice(): void {
    device.value = device.value === 'cuda' ? 'cpu' : 'cuda'
    localStorage.setItem(DEVICE_KEY, device.value)
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
    state.value = 'recording'
  }

  async function transcribe(audio: Blob): Promise<void> {
    state.value = 'transcribing'
    try {
      const { text } = await api.dictate(audio, device.value)
      browserFallback.value = false
      if (text) onText(text)
    } catch (error) {
      browserFallback.value = BrowserRecognition !== undefined
      onError(error)
    } finally {
      state.value = 'idle'
    }
  }

  /** Microphone button: start recording, or stop it and transcribe. */
  function toggleWhisper(): void {
    if (state.value === 'recording') recorder?.stop()
    else if (state.value === 'idle') startRecording().catch(onError)
  }

  async function startListening(): Promise<void> {
    if (BrowserRecognition === undefined) return
    const { language } = await api.dictationSettings()
    recognition = new BrowserRecognition()
    recognition.lang = language
    recognition.continuous = true
    recognition.interimResults = false
    recognition.onresult = (event) => {
      for (let index = event.resultIndex; index < event.results.length; index++) {
        const result = event.results[index]
        if (result.isFinal) onText(result[0].transcript.trim())
      }
    }
    recognition.onerror = (event) => onError(new Error(event.error))
    recognition.onend = () => {
      state.value = 'idle'
    }
    recognition.start()
    state.value = 'listening'
  }

  /** Fallback button: the browser's own recognition, until pressed again. */
  function toggleBrowser(): void {
    if (state.value === 'listening') recognition?.stop()
    else if (state.value === 'idle') startListening().catch(onError)
  }

  return { state, device, browserFallback, toggleDevice, toggleWhisper, toggleBrowser }
}
