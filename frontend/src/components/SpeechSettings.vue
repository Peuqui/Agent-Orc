<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatFactor } from '../format'
import { NEUTRAL_SPEECH_RATE, useSettings, useSpeechVoice } from '../composables/useSettings'
import { useSpeech } from '../composables/useSpeech'
import { useToast } from '../composables/useToast'
import { speechEngines, type VoiceChoice } from '../speech'
import SelectMenu from './SelectMenu.vue'
import ToggleSwitch from './ToggleSwitch.vue'

// Reading answers aloud, for this device: the engine (once more than one is offered), what is
// chosen with it (a voice, a room), speed, the agent's name before its answer, and how much of
// an answer without a paragraph for listening is read. A section of the settings menu.
const emit = defineEmits<{ configure: [] }>()
const MIN_RATE = 0.6
const MAX_RATE = 1.8
const RATE_STEP = 0.1
const { speechEngine, speechRate, speechMaxChars, speechAnnounceName } = useSettings()
const speech = useSpeech()
const toast = useToast()
const { t, locale } = useI18n()
const choices = ref<VoiceChoice[]>([])
// What is chosen is kept for each engine.
const choice = computed({
  get: () => useSpeechVoice(speechEngine.value).value,
  set: (value: string) => {
    useSpeechVoice(speechEngine.value).value = value
  },
})
const choiceOptions = computed(() => [
  { value: '', label: t('answers.voiceDefault') },
  ...choices.value.map((entry) => ({ value: entry.id, label: entry.label })),
])
// The speed slider is an override: at "Normal" nothing is sent and the service's own values (per engine and voice) apply.
const speedLabel = computed(() => {
  const forService = speech.engine.value?.id === 'tts-suite'
  if (!forService) return t('answers.speed', { rate: formatFactor(speechRate.value, locale.value) })
  return speechRate.value === NEUTRAL_SPEECH_RATE
    ? t('answers.speedServiceNormal')
    : t('answers.speedServiceOverride', { rate: formatFactor(speechRate.value, locale.value) })
})
const choiceLabel = computed(() => speech.engine.value?.choiceLabel ?? 'answers.voice')

async function loadChoices(): Promise<void> {
  try {
    choices.value = await speech.choices()
  } catch (error) {
    toast.error(error)
  }
}

onMounted(loadChoices)
watch(speechEngine, loadChoices)
</script>

<template>
  <div v-if="speech.available.value" class="mt-3 flex flex-col gap-2 border-t border-slate-700 pt-3 text-sm text-slate-300">
    <h3 class="font-semibold text-slate-200">{{ $t('answers.speechTitle') }}</h3>
    <label v-if="speechEngines.length > 1" class="flex flex-col gap-1 text-slate-400">
      {{ $t('answers.engine') }}
      <SelectMenu
        v-model="speechEngine"
        :options="speechEngines.map((engine) => ({ value: engine.id, label: engine.label }))"
        button-class="input text-sm text-slate-200"
      />
    </label>
    <button v-if="speech.engine.value?.hasSettings" class="btn-secondary btn-small w-full justify-center" @click="emit('configure')">
      {{ $t('ttsSettings.open') }}
    </button>
    <label v-else class="flex flex-col gap-1 text-slate-400">
      {{ $t(choiceLabel) }}
      <SelectMenu v-model="choice" :options="choiceOptions" button-class="input text-sm text-slate-200" />
    </label>
    <label class="flex flex-col gap-1 text-slate-400">
      <span class="flex justify-between">
        {{ speedLabel }}
        <button type="button" class="text-xs underline" @click="speechRate = NEUTRAL_SPEECH_RATE">{{ $t('answers.speedReset') }}</button>
      </span>
      <input v-model.number="speechRate" type="range" :min="MIN_RATE" :max="MAX_RATE" :step="RATE_STEP" />
    </label>
    <ToggleSwitch class="h-7 self-start text-slate-300" :checked="speechAnnounceName" @click="speechAnnounceName = !speechAnnounceName">
      {{ $t('answers.announceName') }}
    </ToggleSwitch>
    <label class="flex flex-col gap-1 text-slate-400">
      {{ $t('answers.maxChars') }}
      <input v-model.number="speechMaxChars" type="number" min="100" step="100" class="input text-sm text-slate-200" />
    </label>
  </div>
</template>
