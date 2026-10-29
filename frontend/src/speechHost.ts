// A workspace column is a page of its own in an iframe: if each page spoke for itself, two columns
// would read at the same time and the header's stop would not reach them. So the page at the top of
// the tab does the reading. Every page hands its answers up; they are read one after the other in
// the order they came, and what comes while one is read waits behind it. Every page hears which
// answer is being read (useSpeech follows it). A column closed meanwhile does not end its answers.
import { i18n } from './i18n'
import { readAhead } from './readAhead'
import { loadServerEngines, type SpeechEngine, speechEngine } from './speech'
import { spokenText } from './speechText'
import { useSettings, useSpeechVoice } from './composables/useSettings'
import { useToast } from './composables/useToast'

const HOST_KEY = 'agentOrcSpeech'

/** This page is the one at the top of the tab: it reads, and pause and stop are here. */
export const READS_HERE = window.self === window.top

/** An answer to read: the id says which one is being read, the text is Markdown. */
export interface Speakable {
  id: string
  text: string
  /** Whose answer it is (the agent's name): spoken first, if the setting asks for it; the Echo
   * names it as the speaker. */
  label: string
}

export type SpeechChanged = (playing: string | null, paused: boolean) => void

interface Host {
  /** Reads the answers after what is queued already; one queued or read now is not taken again. `done`
   * hears of each answer once it has been read to its end (not of one that was stopped). */
  enqueue: (items: Speakable[], page: Window, done?: (item: Speakable) => void) => void
  /** Ends what is read now and everything queued. */
  stop: () => void
  togglePause: () => void
  /** `changed` now and whenever the answer being read or the pause changes; returns the end of watching. */
  watch: (page: Window, changed: SpeechChanged) => () => void
}

interface Batch {
  items: Speakable[]
  page: Window
  done?: (item: Speakable) => void
}

const queue: Batch[] = []
// Ids queued or being read: an answer asked for twice is read once.
const pending = new Set<string>()
const watchers = new Set<{ page: Window; changed: SpeechChanged }>()
let playing: string | null = null
let paused = false
let running = false
// Counts readings: one that was stopped sees a newer number and ends.
let reading = 0
// The engine reading now, for pause and stop.
let speaker: SpeechEngine | undefined

function tell(): void {
  for (const watcher of watchers) {
    // A removed iframe's window reports itself closed; its functions may not be called any more.
    if (watcher.page.closed) watchers.delete(watcher)
    else watcher.changed(playing, paused)
  }
}

function setPlaying(id: string | null): void {
  playing = id
  tell()
}

function finished(batch: Batch, item: Speakable): void {
  if (!batch.page.closed) batch.done?.(item)
}

async function readBatch(batch: Batch): Promise<void> {
  const mine = reading
  const { speechEngine: engineId, speechRate, speechPitch, speechMaxChars, speechAnnounceName } = useSettings()
  const { t, locale } = i18n.global
  await loadServerEngines()
  if (reading !== mine) return
  const engine = speechEngine(engineId.value)
  speaker = engine
  const limit = Math.min(speechMaxChars.value, engine.maxChars)
  const options = {
    voice: useSpeechVoice(engineId.value).value,
    rate: speechRate.value,
    pitch: speechPitch.value,
    lang: locale.value,
  }
  const answers = batch.items.map((item) => {
    const name = speechAnnounceName.value ? `${item.label}.\n` : ''
    // The name counts towards what the engine takes.
    const answer = spokenText(item.text, t('answers.skipped'), limit - name.length)
    return { item, text: name + answer }
  })
  if (engine.speakAll) {
    // All answers as one announcement: nothing is known of when each one is spoken.
    setPlaying(batch.items[0].id)
    const texts = answers.flatMap((answer) => engine.split(answer.text))
    await engine.speakAll(texts, options, batch.items[0].label)
    if (reading === mine) batch.items.forEach((item) => finished(batch, item))
  } else if (engine.begin) {
    const begin = engine.begin
    await readAhead(answers, {
      begin: (text) => begin(text, options),
      active: () => reading === mine,
      started: (item) => setPlaying(item.id),
      finished: (item) => finished(batch, item),
    })
  } else {
    for (const { item, text } of answers) {
      setPlaying(item.id)
      for (const chunk of engine.split(text)) {
        if (reading !== mine) return
        await engine.speak(chunk, options)
      }
      if (reading !== mine) return
      finished(batch, item)
    }
  }
}

async function run(): Promise<void> {
  running = true
  for (let batch = queue.shift(); batch !== undefined; batch = queue.shift()) {
    try {
      await readBatch(batch)
    } catch (error) {
      useToast().error(error)
    }
    batch.items.forEach((item) => pending.delete(item.id))
  }
  running = false
  paused = false
  setPlaying(null)
}

function enqueue(items: Speakable[], page: Window, done?: (item: Speakable) => void): void {
  const fresh = items.filter((item) => !pending.has(item.id))
  if (fresh.length === 0) return
  fresh.forEach((item) => pending.add(item.id))
  queue.push({ items: fresh, page, done })
  if (!running) void run()
}

function stop(): void {
  reading++
  queue.length = 0
  pending.clear()
  speaker?.cancel()
  paused = false
  setPlaying(null)
}

function togglePause(): void {
  if (playing === null) return
  paused = !paused
  if (paused) speaker?.pause()
  else speaker?.resume()
  tell()
}

function watch(page: Window, changed: SpeechChanged): () => void {
  const watcher = { page, changed }
  watchers.add(watcher)
  changed(playing, paused)
  return () => watchers.delete(watcher)
}

/** Called once as the app starts: on the page at the top of the tab, the reading is done here. */
export function hostSpeech(): void {
  if (READS_HERE) (window as unknown as Record<string, Host>)[HOST_KEY] = { enqueue, stop, togglePause, watch }
}

/** The reading on the page at the top of the tab. */
export function speechHost(): Host {
  return ((window.top ?? window) as unknown as Record<string, Host>)[HOST_KEY]
}
