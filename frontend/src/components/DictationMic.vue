<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Dictation } from '../composables/useDictation'
import { TOUCH_FIRST } from '../device'
import AppIcon from './AppIcon.vue'
import DictationBadge from './DictationBadge.vue'
import DictationPointer from './DictationPointer.vue'

// The microphone, large where it is pressed with a finger. Where the STT-Suite listens (CPU or GPU) and whether a
// dictation goes to the agent at once are set in the settings menu; only the GPU is shown here, as a small
// mark, since it is the exception. With the browser chosen, or without a service, it listens through the browser.
// While a dictation runs, the STT-Suite's badge shows it: with a mouse beside the pointer, on a touch screen in
// the microphone's place. A running dictation is thrown away with Escape (on a touch screen: DictationCancel).
const props = defineProps<{ dictation: Dictation }>()
const busy = computed(() => props.dictation.state === 'transcribing')
const shown = computed(() => props.dictation.active || busy.value)
// The GPU is shown while the service has a model there and the dictation may use it (GPU or automatic).
const onGpu = computed(
  () => props.dictation.engine === 'stt-suite' && props.dictation.device !== 'cpu' && props.dictation.gpuLoaded,
)
// Where the pointer pressed the microphone: the badge starts there.
const pressedAt = ref({ x: 0, y: 0 })

function press(event: MouseEvent): void {
  // Pressed by a key (Enter, Space): no pointer position, so the button's middle.
  const button = (event.currentTarget as HTMLElement).getBoundingClientRect()
  pressedAt.value =
    event.detail === 0
      ? { x: button.left + button.width / 2, y: button.top + button.height / 2 }
      : { x: event.clientX, y: event.clientY }
  props.dictation.toggleMicrophone()
}
</script>

<template>
  <span v-if="dictation.microphone" class="relative flex">
    <button
      type="button"
      class="btn-icon"
      :class="[
        TOUCH_FIRST.matches ? 'size-14' : 'size-11',
        dictation.active ? 'text-accent-500' : 'text-highlight-300',
        { 'animate-pulse': dictation.active && !TOUCH_FIRST.matches, 'opacity-50': busy && !TOUCH_FIRST.matches },
      ]"
      :disabled="busy"
      :aria-label="dictation.active ? $t('dictation.stop') : $t('dictation.start')"
      :title="dictation.active ? $t('dictation.stop') : $t('dictation.start')"
      @click="press"
    >
      <DictationBadge v-if="shown && TOUCH_FIRST.matches" :listening="dictation.active" class="size-10" />
      <AppIcon v-else name="mic" :class="TOUCH_FIRST.matches ? 'size-8' : 'size-6'" />
    </button>
    <DictationPointer
      v-if="shown && !TOUCH_FIRST.matches"
      :listening="dictation.active"
      :x="pressedAt.x"
      :y="pressedAt.y"
    />
    <span
      v-if="onGpu"
      class="pointer-events-none absolute -top-0.5 -right-0.5 rounded border border-highlight-500 px-1 text-[0.55rem] leading-3.5 font-semibold text-highlight-300"
      :title="$t('settings.dictationDeviceGpu')"
    >
      GPU
    </span>
  </span>
</template>
