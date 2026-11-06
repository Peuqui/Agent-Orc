import { rootAddress } from './api'

// The tones around the microphone: a higher "ping" when listening starts, a lower "pong" when it stops, and the
// puck's "break" when a dictation is cancelled.
// Either the Echo puck's recordings (public/sounds/, from FreeEchoDot2's audio_samples at 37190a9, made
// by its tools/gen_notify_sounds.py), so both sound alike, or sine beeps made in the browser, as AIfred
// plays them.
export type Signal = 'start' | 'stop' | 'cancel'

/** Which tones a device plays (its own choice: the puck's sound richer on a large speaker, less clean on a
 * phone's). */
export type DictationSounds = 'puck' | 'sine'

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
// Where a recording's sound counts as over: its last moment above this share of its peak (-20 dB). The rest is
// the reverb's tail, which an opening microphone may cut short without it being missed.
const HEARD_SHARE_OF_PEAK = 0.1

/** A recording, and how long its sound is heard (see HEARD_SHARE_OF_PEAK). */
interface Recording {
  buffer: AudioBuffer
  heardSeconds: number
}

// Each recording is fetched and decoded once, then played from memory: a tone at once, without the network.
const decoded = new Map<Signal, Promise<Recording>>()
// Decoded without an audio output, at the recordings' own rate (48 kHz); a tone's context plays it at its own.
const DECODE_SAMPLE_RATE = 48000

function heardSeconds(buffer: AudioBuffer): number {
  const channels = Array.from({ length: buffer.numberOfChannels }, (_, index) => buffer.getChannelData(index))
  const loudness = (at: number): number => Math.max(...channels.map((samples) => Math.abs(samples[at])))
  let peak = 0
  for (let at = 0; at < buffer.length; at++) peak = Math.max(peak, loudness(at))
  let last = buffer.length - 1
  while (last > 0 && loudness(last) < peak * HEARD_SHARE_OF_PEAK) last--
  return (last + 1) / buffer.sampleRate
}

function recording(signal: Signal): Promise<Recording> {
  let found = decoded.get(signal)
  if (found === undefined) {
    found = fetch(new URL(RECORDINGS[signal], rootAddress()))
      .then((response) => {
        if (!response.ok) throw new Error(`${RECORDINGS[signal]}: ${response.status}`)
        return response.arrayBuffer()
      })
      .then((data) => new OfflineAudioContext(1, 1, DECODE_SAMPLE_RATE).decodeAudioData(data))
      .then((buffer) => ({ buffer, heardSeconds: heardSeconds(buffer) }))
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
}

/** Plays the tone; done once its sound is heard to its end, before the reverb's tail (the microphone opens
 * then, see useDictation). Each tone has a context of its own, closed after it: a phone switches a context to
 * a call's audio path once the microphone was used and kept it there (the tones sounded distorted and the
 * end's came late, after waking it); a new one never sits there, and nothing keeps the audio output awake. */
export async function playSignal(signal: Signal, sounds: DictationSounds): Promise<void> {
  const found = sounds === 'puck' ? await recording(signal) : null
  const tone = new AudioContext()
  // Made outside a tap (the end's tone after the recorder), a context may start suspended.
  await tone.resume()
  const source = found === null ? startBeep(tone, BEEPS[signal]) : startRecording(tone, found.buffer)
  source.onended = () => void tone.close()
  const heard = found === null ? BEEPS[signal].milliseconds / MILLISECONDS_PER_SECOND : found.heardSeconds
  await new Promise((heardOut) => window.setTimeout(heardOut, heard * MILLISECONDS_PER_SECOND))
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
  // On the new context's clock: from now.
  const now = tone.currentTime
  const end = now + beep.milliseconds / MILLISECONDS_PER_SECOND
  gain.gain.setValueAtTime(BEEP_VOLUME, now)
  gain.gain.exponentialRampToValueAtTime(FADE_TO, end)
  oscillator.start(now)
  oscillator.stop(end)
  return oscillator
}
