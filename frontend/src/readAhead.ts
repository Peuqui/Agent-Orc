// Reading several answers with an engine that works ahead (see SpeechEngine.begin): the next answer
// is sent as soon as the one before is here, not when it has been played, so the engine is making
// it while the one before is spoken.
import type { SpeechJob } from './speech'

export interface ReadAheadCallbacks<T> {
  /** Sends the text of an answer; the audio queues behind what was begun before. */
  begin: (text: string) => SpeechJob
  /** False once the reading was stopped or another one began: nothing more is sent or reported. */
  active: () => boolean
  /** The answer is being spoken now (the one before has ended). */
  started: (item: T) => void
  /** The answer was spoken to its end. */
  finished: (item: T) => void
}

export async function readAhead<T>(answers: { item: T; text: string }[], callbacks: ReadAheadCallbacks<T>): Promise<void> {
  let previousReceived: Promise<void> = Promise.resolve()
  const jobs = answers.map(({ text }) => {
    const job = previousReceived.then(() => (callbacks.active() ? callbacks.begin(text) : undefined))
    previousReceived = job.then((began) => began?.received)
    // The failure of one is thrown where its turn comes below; the ones after it only repeat it.
    job.catch(() => undefined)
    previousReceived.catch(() => undefined)
    return job
  })
  for (const [index, { item }] of answers.entries()) {
    const job = await jobs[index]
    if (!callbacks.active() || job === undefined) return
    callbacks.started(item)
    await job.ended
    if (!callbacks.active()) return
    callbacks.finished(item)
  }
}
