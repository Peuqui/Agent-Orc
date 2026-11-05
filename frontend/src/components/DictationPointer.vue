<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import DictationBadge from './DictationBadge.vue'

// With a mouse: the badge goes along with the pointer while a dictation runs (a browser cannot animate the
// pointer itself), below and right of it, as SpeechPulse shows its own. It takes no clicks: the microphone
// under the pointer ends the dictation as before.
const props = defineProps<{ listening: boolean; x: number; y: number }>()
// Below and right of the pointer's tip, clear of the pointer itself.
const OFFSET_PX = 18
const position = ref({ x: props.x, y: props.y })

function follow(event: PointerEvent): void {
  position.value = { x: event.clientX, y: event.clientY }
}
onMounted(() => window.addEventListener('pointermove', follow, { passive: true }))
onBeforeUnmount(() => window.removeEventListener('pointermove', follow))
</script>

<template>
  <Teleport to="body">
    <DictationBadge
      :listening="listening"
      class="pointer-events-none fixed z-[60] size-7 drop-shadow"
      :style="{ left: `${position.x + OFFSET_PX}px`, top: `${position.y + OFFSET_PX}px` }"
    />
  </Teleport>
</template>
