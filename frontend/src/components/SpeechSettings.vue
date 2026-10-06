<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { DEFAULT_SPEECH_RATE, useSettings } from '../composables/useSettings'
import { useSpeech } from '../composables/useSpeech'
import { useToast } from '../composables/useToast'
import type { VoiceChoice } from '../speech'
import ToggleSwitch from './ToggleSwitch.vue'

// Reading answers aloud, for this device: engine (once more than one is offered), voice, speed,
// the agent's name before its answer, and how much of an answer without a paragraph for
// listening is read. A section of the settings menu.
const MIN_RATE = 0.6
const MAX_RATE = 1.8
const RATE_STEP = 0.1
const { speechEngine, speechVoice, speechRate, speechMaxChars, speechAnnounceName } = useSettings()
const speech = useSpeech()
const toast = useToast()
const voices = ref<VoiceChoice[]>([])

onMounted(async () => {
  try {
    voices.value = await speech.voices()
  } catch (error) {
    toast.error(error)
  }
})
</script>

<template>
  <div v-if="speech.available" class="mt-3 flex flex-col gap-2 border-t border-slate-700 pt-3 text-sm text-slate-300">
    <h3 class="font-semibold text-slate-200">{{ $t('answers.speechTitle') }}</h3>
    <label v-if="speech.engines.length > 1" class="flex flex-col gap-1 text-slate-400">
      {{ $t('answers.engine') }}
      <select v-model="speechEngine" class="input text-sm text-slate-200">
        <option v-for="engine in speech.engines" :key="engine.id" :value="engine.id">{{ engine.label }}</option>
      </select>
    </label>
    <label class="flex flex-col gap-1 text-slate-400">
      {{ $t('answers.voice') }}
      <select v-model="speechVoice" class="input text-sm text-slate-200">
        <option value="">{{ $t('answers.voiceDefault') }}</option>
        <option v-for="voice in voices" :key="voice.id" :value="voice.id">{{ voice.label }}</option>
      </select>
    </label>
    <label class="flex flex-col gap-1 text-slate-400">
      <span class="flex justify-between">
        {{ $t('answers.speed', { rate: speechRate.toFixed(1) }) }}
        <button type="button" class="text-xs underline" @click="speechRate = DEFAULT_SPEECH_RATE">{{ $t('answers.speedReset') }}</button>
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
