<script setup lang="ts">
import { dictationPointerState } from '../dictationPointer'
import DictationBadge from './DictationBadge.vue'

// With a mouse: the badge goes along with the pointer while a dictation runs anywhere in the tab (a browser
// cannot animate the pointer itself, nor draw outside its window), above and right of it: below it the browser
// draws the microphone's tooltip, over everything. It takes no clicks: the microphone under the pointer ends
// the dictation as before. On the page at the top of the tab only (dictationPointer.ts).
const badge = dictationPointerState()
// Right of the pointer's tip and above it, clear of the pointer itself and of the tooltip below it.
const RIGHT_PX = 14
const ABOVE_PX = 38
</script>

<template>
  <DictationBadge
    v-if="badge.shown"
    :listening="badge.listening"
    class="pointer-events-none fixed z-[60] size-7 drop-shadow"
    :style="{ left: `${badge.x + RIGHT_PX}px`, top: `${badge.y - ABOVE_PX}px` }"
  />
</template>
