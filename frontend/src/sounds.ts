// Short sine beeps generated in the browser, as AIfred plays them around its microphone:
// a higher "ping" when listening starts, a lower "pong" when it stops.
export const START_BEEP = { frequency: 1000, milliseconds: 150 }
export const STOP_BEEP = { frequency: 600, milliseconds: 200 }
const VOLUME = 0.3
// The tone fades out exponentially to this level, which cannot be zero.
const FADE_TO = 0.01
const MILLISECONDS_PER_SECOND = 1000

export function playBeep(beep: { frequency: number; milliseconds: number }): void {
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
