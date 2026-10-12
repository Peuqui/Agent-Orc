<script setup lang="ts">
import { computed } from 'vue'
import type { Dictation } from '../composables/useDictation'
import { TOUCH_FIRST } from '../device'
import AppIcon from './AppIcon.vue'

// The microphone, large where it is pressed with a finger. Where Whisper listens (CPU or GPU) and whether a
// dictation goes to the agent at once are set in the settings menu; only the GPU is shown here, as a small
// mark, since it is the exception. Without Whisper the microphone listens through the browser.
const props = defineProps<{ dictation: Dictation }>()
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
const onGpu = computed(() => props.dictation.whisper === true && props.dictation.device === 'cuda')
</script>

<template>
  <span v-if="dictation.microphone" class="relative flex">
    <button
      type="button"
      class="btn-icon"
      :class="[TOUCH_FIRST.matches ? 'size-14' : 'size-11', active ? 'animate-pulse text-red-500' : 'text-amber-300', { 'opacity-50': busy }]"
      :disabled="busy"
      :aria-label="active ? $t('dictation.stop') : $t('dictation.start')"
      :title="active ? $t('dictation.stop') : $t('dictation.start')"
      @click="dictation.toggleMicrophone"
    >
      <AppIcon name="mic" :class="TOUCH_FIRST.matches ? 'size-8' : 'size-6'" />
    </button>
    <span
      v-if="onGpu"
      class="pointer-events-none absolute -top-0.5 -right-0.5 rounded border border-amber-500 px-1 text-[0.55rem] leading-3.5 font-semibold text-amber-300"
      :title="$t('settings.dictationDeviceGpu')"
    >
      GPU
    </span>
  </span>
</template>
