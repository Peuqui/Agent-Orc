import type { DictationSounds } from './api'

// The tones around the microphone: a higher "ping" when listening starts, a lower "pong" when it stops.
// Either the Echo puck's recordings (public/sounds/, from FreeEchoDot2's audio_samples at 37190a9, made
// by its tools/gen_notify_sounds.py), so both sound alike, or sine beeps made in the browser, as AIfred
// plays them.
export type Signal = 'start' | 'stop'

const RECORDINGS: Record<Signal, string> = { start: 'sounds/ping.wav', stop: 'sounds/pong.wav' }
const BEEPS: Record<Signal, { frequency: number; milliseconds: number }> = {
  start: { frequency: 1000, milliseconds: 150 },
  stop: { frequency: 600, milliseconds: 200 },
}
const VOLUME = 0.3
// The tone fades out exponentially to this level, which cannot be zero.
const FADE_TO = 0.01
const MILLISECONDS_PER_SECOND = 1000

export function playSignal(signal: Signal, sounds: DictationSounds): void {
  if (sounds === 'puck') playRecording(signal)
  else playBeep(BEEPS[signal])
}

// Loaded once, then played again from the start.
const loaded = new Map<Signal, HTMLAudioElement>()

function playRecording(signal: Signal): void {
  let audio = loaded.get(signal)
  if (audio === undefined) {
    audio = new Audio(new URL(RECORDINGS[signal], document.baseURI).href)
    loaded.set(signal, audio)
  }
  audio.currentTime = 0
  void audio.play()
}

function playBeep(beep: { frequency: number; milliseconds: number }): void {
  const context = new AudioContext()
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.type = 'sine'
  oscillator.frequency.value = beep.frequency
  const end = context.currentTime + beep.milliseconds / MILLISECONDS_PER_SECOND
  gain.gain.setValueAtTime(VOLUME, context.currentTime)
  gain.gain.exponentialRampToValueAtTime(FADE_TO, end)
  oscillator.onended = () => void context.close()
  oscillator.start(context.currentTime)
  oscillator.stop(end)
}
