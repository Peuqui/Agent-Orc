<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import type { Dictation } from '../composables/useDictation'
import { TOUCH_FIRST } from '../device'
import DictationBadge, { type BadgePhase } from './DictationBadge.vue'
import { dictationPointer } from '../dictationPointer'

// The microphone; on a touch screen as large as the field and the buttons beside it (40 px), so the row keeps
// their height. Where the STT-Suite listens (CPU or GPU) and whether a
// dictation goes to the agent at once are set in the settings menu; only the GPU is shown here, as a small
// mark, since it is the exception. With the browser chosen, or without a service, it listens through the browser.
// The button is the STT-Suite's badge, without a background of its own (also under the pointer), which shows how
// the dictation stands (ready, taking speech in, transcribing); with a mouse it goes along with the pointer, too,
// anywhere in the tab (dictationPointer.ts). A running dictation is thrown away with Escape (on a touch screen:
// DictationCancel).
const props = defineProps<{ dictation: Dictation }>()
const busy = computed(() => props.dictation.state === 'transcribing')
const shown = computed(() => props.dictation.active || busy.value)
const phase = computed<BadgePhase>(() => (props.dictation.active ? 'listening' : busy.value ? 'transcribing' : 'ready'))
// The GPU is shown while the service has a model there and the dictation may use it (GPU or automatic): as a small
// plate with the page's own background, so the badge's waves do not show through it, grey while it is transcribed (as the badge).
const onGpu = computed(
  () => props.dictation.engine === 'stt-suite' && props.dictation.device !== 'cpu' && props.dictation.gpuLoaded,
)
const pointer = dictationPointer()
// Where the pointer pressed the microphone: the badge starts there.
let pressedAt = { x: 0, y: 0 }
watch(shown, (now) => {
  if (TOUCH_FIRST.matches) return
  if (now) pointer.set(props.dictation.active, pressedAt.x, pressedAt.y)
  else pointer.set(null)
})
watch(
  () => props.dictation.active,
  (active) => shown.value && !TOUCH_FIRST.matches && pointer.set(active),
)
onBeforeUnmount(() => pointer.set(null))

function press(event: MouseEvent): void {
  // Pressed by a key (Enter, Space): no pointer position, so the button's middle.
  const button = (event.currentTarget as HTMLElement).getBoundingClientRect()
  pressedAt =
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
      class="inline-flex items-center justify-center disabled:opacity-30"
      :class="TOUCH_FIRST.matches ? 'size-10' : 'size-11'"
      :disabled="busy"
      :aria-label="dictation.active ? $t('dictation.stop') : $t('dictation.start')"
      :title="dictation.active ? $t('dictation.stop') : $t('dictation.start')"
      @click="press"
    >
      <DictationBadge :phase="phase" :class="TOUCH_FIRST.matches ? 'size-9' : 'size-8'" />
    </button>
    <span
      v-if="onGpu"
      class="pointer-events-none absolute -top-0.5 -right-0.5 rounded border bg-page px-1 text-[0.5rem] leading-3 font-semibold"
      :class="busy ? 'border-slate-500 text-slate-400' : 'border-highlight-500 text-highlight-300'"
      :title="$t('settings.dictationDeviceGpu')"
    >
      GPU
    </span>
  </span>
</template>
