<script setup lang="ts">
import { computed } from 'vue'
import ContextRing from './ContextRing.vue'

// A usage (context window, account limit) as a small ring with its percentage; where there is
// room, a longer text replaces the bare percentage. The text stays grey: only the ring carries
// the warning colour (coloured text looked larger than the grey rows).
const props = defineProps<{
  /** 0 to 100. */
  percent: number
  /** Shown on hover or tap. */
  title: string
  detail?: string
  /** What decides the room: the window (sm and up), or the nearest @container. */
  roomOf?: 'window' | 'container'
}>()

// Whole class names, so Tailwind finds them.
const DETAIL_SHOWN = { window: 'hidden sm:inline', container: 'hidden @[15rem]:inline' }
const PERCENT_HIDDEN = { window: 'sm:hidden', container: '@[15rem]:hidden' }
const room = computed(() => props.roomOf ?? 'window')
</script>

<template>
  <span class="inline-flex shrink-0 items-center gap-1.5 text-xs whitespace-nowrap text-slate-400" :title="title">
    <ContextRing :percent="percent" />
    <span v-if="detail" :class="DETAIL_SHOWN[room]">{{ detail }}</span>
    <span :class="detail ? PERCENT_HIDDEN[room] : ''">{{ Math.round(percent) }} %</span>
  </span>
</template>
