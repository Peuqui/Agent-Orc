import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { loadServerEngines, speechEngine, speechEngines } from '../speech'
import { spokenText } from '../speechText'
import { useSettings, useSpeechVoice } from './useSettings'
import { useToast } from './useToast'

/** An answer to read: the id says which one is being read, the text is Markdown. */
export interface Speakable {
  id: string
  text: string
  /** Whose answer it is (the agent's name): spoken first, if the setting asks for it. */
  label?: string
}

// One reading at a time on the device, whichever view started it.
const playing = ref<string | null>(null)
const paused = ref(false)
let reading = 0

export function useSpeech() {
  const { speechEngine: engineId, speechRate, speechMaxChars, speechAnnounceName } = useSettings()
  const { locale, t } = useI18n()
  const toast = useToast()
  // Not there while the server's engines are still being asked for (see loadServerEngines).
  const engine = computed(() => speechEngines.value.find((candidate) => candidate.id === engineId.value))
  const voice = computed(() => useSpeechVoice(engineId.value))
  const available = computed(() => speechEngines.value.length > 0)

  /** Reads the answers one after the other; what is read now ends. */
  async function play(items: Speakable[]): Promise<void> {
    stop()
    const mine = ++reading
    try {
      await loadServerEngines()
      const speaker = speechEngine(engineId.value)
      const limit = Math.min(speechMaxChars.value, speaker.maxChars)
      const options = { voice: voice.value.value, rate: speechRate.value, lang: locale.value }
      const answers = items.map((item) => {
        const name = speechAnnounceName.value && item.label ? `${item.label}.\n` : ''
        // The name counts towards what the engine takes.
        const answer = spokenText(item.text, t('answers.skipped'), limit - name.length)
        return { item, text: name + answer }
      })
      if (speaker.speakAll) {
        // All answers as one announcement: nothing is known of when each one is spoken.
        playing.value = items[0]?.id ?? null
        const texts = answers.flatMap((answer) => speaker.split(answer.text))
        await speaker.speakAll(texts, options, items[0]?.label ?? '')
      } else {
        for (const { item, text } of answers) {
          playing.value = item.id
          for (const chunk of speaker.split(text)) {
            if (reading !== mine) return
            await speaker.speak(chunk, options)
          }
        }
      }
    } catch (error) {
      toast.error(error)
    }
    if (reading === mine) stop()
  }

  function stop(): void {
    reading++
    engine.value?.cancel()
    playing.value = null
    paused.value = false
  }

  function togglePause(): void {
    if (playing.value === null) return
    paused.value = !paused.value
    if (paused.value) engine.value?.pause()
    else engine.value?.resume()
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
    stop,
    togglePause,
  }
}
