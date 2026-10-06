<script setup lang="ts">
import { ref } from 'vue'
import { DEFAULT_SPEECH_RATE, useSettings } from '../composables/useSettings'
import { useSpeech } from '../composables/useSpeech'
import { useToast } from '../composables/useToast'
import type { VoiceChoice } from '../speech'
import AppIcon from './AppIcon.vue'

// Voice and speed of the speech output, and the engine once a device offers more than one.
const MIN_RATE = 0.6
const MAX_RATE = 1.8
const RATE_STEP = 0.1
const { speechEngine, speechVoice, speechRate } = useSettings()
const speech = useSpeech()
const toast = useToast()
const open = ref(false)
const voices = ref<VoiceChoice[]>([])

async function show(): Promise<void> {
  open.value = !open.value
  if (!open.value) return
  try {
    voices.value = await speech.voices()
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <button type="button" class="btn-secondary btn-small-icon" :title="$t('answers.voice')" :aria-label="$t('answers.voice')" @click="show">
    <AppIcon name="settings" />
  </button>
  <div v-if="open" class="card fixed inset-x-3 top-24 z-40 flex max-w-sm flex-col gap-3 p-3 shadow-xl sm:left-auto">
    <label v-if="speech.engines.length > 1" class="flex flex-col gap-1 text-sm text-slate-400">
      {{ $t('answers.engine') }}
      <select v-model="speechEngine" class="input text-sm text-slate-200">
        <option v-for="engine in speech.engines" :key="engine.id" :value="engine.id">{{ engine.label }}</option>
      </select>
    </label>
    <label class="flex flex-col gap-1 text-sm text-slate-400">
      {{ $t('answers.voice') }}
      <select v-model="speechVoice" class="input text-sm text-slate-200">
        <option value="">{{ $t('answers.voiceDefault') }}</option>
        <option v-for="voice in voices" :key="voice.id" :value="voice.id">{{ voice.label }}</option>
      </select>
    </label>
    <label class="flex flex-col gap-1 text-sm text-slate-400">
      {{ $t('answers.speed', { rate: speechRate.toFixed(1) }) }}
      <input v-model.number="speechRate" type="range" :min="MIN_RATE" :max="MAX_RATE" :step="RATE_STEP" />
    </label>
    <div class="flex justify-between">
      <button type="button" class="btn-secondary btn-small" @click="speechRate = DEFAULT_SPEECH_RATE">{{ $t('answers.speedReset') }}</button>
      <button type="button" class="btn-primary btn-small" @click="open = false">{{ $t('common.close') }}</button>
    </div>
  </div>
</template>
