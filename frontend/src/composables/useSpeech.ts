import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { loadServerEngines, speechEngine, speechEngines } from '../speech'
import { type Speakable, speechHost } from '../speechHost'
import { useSettings } from './useSettings'

// What the page at the top of the tab reads now (speechHost.ts), followed on this page.
const playing = ref<string | null>(null)
const paused = ref(false)
let stopWatching: (() => void) | undefined

function followHost(): void {
  if (stopWatching !== undefined) return
  stopWatching = speechHost().watch(window, (now, pausedNow) => {
    playing.value = now
    paused.value = pausedNow
  })
  // A column loaded anew is the same window to the host: the page that leaves stops being told.
  window.addEventListener('pagehide', () => stopWatching?.(), { once: true })
}

export function useSpeech() {
  const { speechEngine: engineId } = useSettings()
  const { locale } = useI18n()
  followHost()
  // Not there while the server's engines are still being asked for (see loadServerEngines).
  const engine = computed(() => speechEngines.value.find((candidate) => candidate.id === engineId.value))
  const available = computed(() => speechEngines.value.length > 0)

  /** Reads the answers after what is being read already (on any page of the tab). `done` hears of each
   * answer once it has been read to its end (not of one that was stopped). */
  function play(items: Speakable[], done?: (item: Speakable) => void): void {
    speechHost().enqueue(items, window, done)
  }

  return {
    available,
    playing,
    paused,
    engines: speechEngines,
    engine,
    /** What can be chosen with the engine now: voices, rooms. */
    choices: async () => {
      await loadServerEngines()
      return speechEngine(engineId.value).voices(locale.value)
    },
    play,
    stop: () => speechHost().stop(),
    togglePause: () => speechHost().togglePause(),
  }
}
