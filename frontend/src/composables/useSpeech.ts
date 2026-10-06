import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { speechEngine, speechEngines } from '../speech'
import { speakableText, speechChunks } from '../speechText'
import { useSettings } from './useSettings'
import { useToast } from './useToast'

/** An answer to read: the id says which one is being read, the text is Markdown. */
export interface Speakable {
  id: string
  text: string
}

// One reading at a time on the device, whichever view started it.
const playing = ref<string | null>(null)
const paused = ref(false)
let reading = 0

export function useSpeech() {
  const { speechEngine: engineId, speechVoice, speechRate } = useSettings()
  const { locale, t } = useI18n()
  const toast = useToast()
  const engine = computed(() => speechEngine(engineId.value))
  const available = speechEngines.length > 0

  /** Reads the answers one after the other; what is read now ends. */
  async function play(items: Speakable[]): Promise<void> {
    stop()
    const mine = ++reading
    try {
      for (const item of items) {
        playing.value = item.id
        const text = speakableText(item.text, t('answers.skipped'))
        for (const chunk of speechChunks(text)) {
          if (reading !== mine) return
          await engine.value.speak(chunk, { voice: speechVoice.value, rate: speechRate.value, lang: locale.value })
        }
      }
    } catch (error) {
      toast.error(error)
    }
    if (reading === mine) stop()
  }

  function stop(): void {
    reading++
    engine.value.cancel()
    playing.value = null
    paused.value = false
  }

  function togglePause(): void {
    if (playing.value === null) return
    paused.value = !paused.value
    if (paused.value) engine.value.pause()
    else engine.value.resume()
  }

  return {
    available,
    playing,
    paused,
    engines: speechEngines,
    engine,
    voices: () => engine.value.voices(locale.value),
    play,
    stop,
    togglePause,
  }
}
