<script setup lang="ts">
import { computed } from 'vue'
import type { Dictation } from '../composables/useDictation'
import { useSettings } from '../composables/useSettings'
import AppIcon from './AppIcon.vue'

// The microphone with the device switch (GPU or CPU) in front of it: the one used most is the
// easiest to hit. Without Whisper the microphone itself listens through the browser. Behind it
// the switch whether a dictation goes to the agent at once (where one decides it, while dictating).
const props = defineProps<{ dictation: Dictation }>()
const { dictationSendsAtOnce } = useSettings()
const active = computed(
  () =>
    props.dictation.state === 'recording' ||
    (props.dictation.whisper === false && props.dictation.state === 'listening'),
)
const busy = computed(
  () =>
    props.dictation.state === 'transcribing' ||
    (props.dictation.whisper === true && props.dictation.state === 'listening'),
)
</script>

<template>
  <template v-if="dictation.microphone">
    <button
      v-if="dictation.whisper"
      type="button"
      class="mb-2 ml-0.5 h-6 rounded border border-slate-600 px-1 text-[0.6rem] font-semibold tracking-wide text-slate-300 hover:border-slate-400"
      :title="$t('dictation.device')"
      :disabled="dictation.state !== 'idle'"
      @click="dictation.toggleDevice"
    >
      {{ dictation.device === 'cuda' ? 'GPU' : 'CPU' }}
    </button>
    <button
      type="button"
      class="btn-icon size-11"
      :class="[active ? 'animate-pulse text-red-500' : 'text-amber-300', { 'opacity-50': busy }]"
      :disabled="busy"
      :aria-label="active ? $t('dictation.stop') : $t('dictation.start')"
      :title="active ? $t('dictation.stop') : $t('dictation.start')"
      @click="dictation.toggleMicrophone"
    >
      <AppIcon name="mic" class="size-6" />
    </button>
    <button
      type="button"
      role="switch"
      class="-ml-1 mb-2 h-6 rounded px-0.5 text-sm"
      :class="dictationSendsAtOnce ? '' : 'opacity-50 grayscale'"
      :aria-checked="dictationSendsAtOnce"
      :aria-label="$t(dictationSendsAtOnce ? 'dictation.sendsAtOnceOn' : 'dictation.sendsAtOnceOff')"
      :title="$t(dictationSendsAtOnce ? 'dictation.sendsAtOnceOn' : 'dictation.sendsAtOnceOff')"
      @click="dictationSendsAtOnce = !dictationSendsAtOnce"
    >
      ⚡
    </button>
  </template>
</template>
