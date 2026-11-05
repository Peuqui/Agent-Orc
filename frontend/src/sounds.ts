import { rootAddress, type DictationSounds } from './api'

// The tones around the microphone: a higher "ping" when listening starts, a lower "pong" when it stops, and the
// puck's "break" when a dictation is cancelled.
// Either the Echo puck's recordings (public/sounds/, from FreeEchoDot2's audio_samples at 37190a9, made
// by its tools/gen_notify_sounds.py), so both sound alike, or sine beeps made in the browser, as AIfred
// plays them.
export type Signal = 'start' | 'stop' | 'cancel'

// From this machine's own app on every machine's page: one address, so the browser holds one copy
// (the service worker keeps it, vite.config.ts).
const RECORDINGS: Record<Signal, string> = {
  start: 'sounds/ping.wav',
  stop: 'sounds/pong.wav',
  cancel: 'sounds/break.wav',
}
const BEEPS: Record<Signal, { frequency: number; milliseconds: number }> = {
  start: { frequency: 1000, milliseconds: 150 },
  stop: { frequency: 600, milliseconds: 200 },
  // Lower and longer than the end: nothing is transcribed.
  cancel: { frequency: 400, milliseconds: 300 },
}
const BEEP_VOLUME = 0.3
// The tone fades out exponentially to this level, which cannot be zero.
const FADE_TO = 0.01
const MILLISECONDS_PER_SECOND = 1000

let context: AudioContext | undefined
let sounding = 0
// Each recording is fetched and decoded once, then played from memory: a tone at once, without the network.
const decoded = new Map<Signal, Promise<AudioBuffer>>()

/** One context for every tone. A context left running plays silence for good, which on a phone keeps the
 * audio output and the processor awake: it sleeps once no tone sounds (as the reading aloud's, speech.ts). */
function audioContext(): AudioContext {
  context ??= new AudioContext()
  return context
}

function recording(signal: Signal): Promise<AudioBuffer> {
  let found = decoded.get(signal)
  if (found === undefined) {
    found = fetch(new URL(RECORDINGS[signal], rootAddress()))
      .then((response) => {
        if (!response.ok) throw new Error(`${RECORDINGS[signal]}: ${response.status}`)
        return response.arrayBuffer()
      })
      .then((data) => audioContext().decodeAudioData(data))
    // A failed load is tried again at the next tone.
    found.catch(() => decoded.delete(signal))
    decoded.set(signal, found)
  }
  return found
}

/** Fetches and decodes the recordings ahead, so the first dictation's tone needs no wait either. */
export async function loadSignals(sounds: DictationSounds): Promise<void> {
  if (sounds !== 'puck') return
  await Promise.all([recording('start'), recording('stop'), recording('cancel')])
  // Decoding made the context, which some browsers start running: it sleeps until the first tone.
  if (sounding === 0) await context?.suspend()
}

export async function playSignal(signal: Signal, sounds: DictationSounds): Promise<void> {
  const tone = audioContext()
  const buffer = sounds === 'puck' ? await recording(signal) : null
  await tone.resume()
  const source = buffer === null ? startBeep(tone, BEEPS[signal]) : startRecording(tone, buffer)
  sounding++
  source.onended = () => {
    sounding--
    if (sounding === 0) void tone.suspend()
  }
}

function startRecording(tone: AudioContext, buffer: AudioBuffer): AudioScheduledSourceNode {
  const source = tone.createBufferSource()
  source.buffer = buffer
  source.connect(tone.destination)
  source.start()
  return source
}

function startBeep(tone: AudioContext, beep: { frequency: number; milliseconds: number }): AudioScheduledSourceNode {
  const oscillator = tone.createOscillator()
  const gain = tone.createGain()
  oscillator.connect(gain)
  gain.connect(tone.destination)
  oscillator.type = 'sine'
  oscillator.frequency.value = beep.frequency
  // On the context's clock, which stood still while it slept: from now.
  const now = tone.currentTime
  const end = now + beep.milliseconds / MILLISECONDS_PER_SECOND
  gain.gain.setValueAtTime(BEEP_VOLUME, now)
  gain.gain.exponentialRampToValueAtTime(FADE_TO, end)
  oscillator.start(now)
  oscillator.stop(end)
  return oscillator
}
