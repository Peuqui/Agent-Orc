<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatFactor } from '../format'
import { useSettings, useSpeechVoice } from '../composables/useSettings'
import { useSpeech } from '../composables/useSpeech'
import { useToast } from '../composables/useToast'
import { speechEngines, type VoiceChoice } from '../speech'
import SelectMenu from './SelectMenu.vue'
import FactorInput from './FactorInput.vue'
import ToggleSwitch from './ToggleSwitch.vue'

// Reading answers aloud, for this device: the engine (once more than one is offered), what is
// chosen with it (a voice, a room), speed, the agent's name before its answer, and how much of
// an answer without a paragraph for listening is read. A section of the settings menu.
const emit = defineEmits<{ configure: [] }>()
const { speechEngine, speechRate, speechPitch, speechMaxChars, speechAnnounceName } = useSettings()
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
// Speed and pitch are overrides. Empty, the TTS service's own values (per engine and voice) apply; the browser's voices speak at 1.
const forService = computed(() => speech.engine.value?.id === 'tts-suite')
const tempoPlaceholder = computed(() => (forService.value ? t('ttsSettings.serviceValue') : formatFactor(1, locale.value)))
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
  <div v-if="speech.available.value" class="flex flex-col gap-3 text-sm text-soft">
    <label v-if="speechEngines.length > 1" class="flex flex-col gap-1 text-dim">
      {{ $t('answers.engine') }}
      <SelectMenu
        v-model="speechEngine"
        :options="speechEngines.map((engine) => ({ value: engine.id, label: engine.label }))"
        button-class="input text-sm text-main"
      />
    </label>
    <button v-if="speech.engine.value?.hasSettings" class="btn-secondary btn-small w-full justify-center" @click="emit('configure')">
      {{ $t('ttsSettings.open') }}
    </button>
    <label v-else class="flex flex-col gap-1 text-dim">
      {{ $t(choiceLabel) }}
      <SelectMenu v-model="choice" :options="choiceOptions" button-class="input text-sm text-main" />
    </label>
    <div v-if="speech.engine.value?.usesTempo" class="flex flex-col gap-1">
      <div class="flex gap-2">
        <label class="flex min-w-0 flex-1 flex-col gap-0.5 text-dim">
          {{ $t('answers.tempo') }}
          <FactorInput v-model="speechRate" :placeholder="tempoPlaceholder" />
        </label>
        <label class="flex min-w-0 flex-1 flex-col gap-0.5 text-dim">
          {{ $t('answers.pitch') }}
          <FactorInput v-model="speechPitch" :placeholder="tempoPlaceholder" />
        </label>
      </div>
      <p class="text-xs text-hint">{{ $t(forService ? 'answers.tempoPitchHintService' : 'answers.tempoPitchHintBrowser') }}</p>
    </div>
    <ToggleSwitch class="h-7 self-start text-soft" :checked="speechAnnounceName" @click="speechAnnounceName = !speechAnnounceName">
      {{ $t('answers.announceName') }}
    </ToggleSwitch>
    <label class="flex flex-col gap-1 text-dim">
      {{ $t('answers.maxChars') }}
      <input v-model.number="speechMaxChars" type="number" min="100" step="100" class="input text-sm text-main" />
    </label>
  </div>
</template>
