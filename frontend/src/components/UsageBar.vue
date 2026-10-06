<script setup lang="ts">
import { computed } from 'vue'
import { usageTone } from '../usage'

// What belongs together stands together: the bar, right next to it the percentage, then (set off
// by a wider gap) when the limit resets.
const props = defineProps<{ label: string; percent: number; reset: string }>()

const tone = computed(() => usageTone(props.percent))
</script>

<template>
  <div class="flex items-center gap-2 text-xs text-slate-400">
    <!-- Fixed widths, so bars stacked in one card line up. -->
    <span class="w-16 shrink-0 whitespace-nowrap">{{ label }}</span>
    <div class="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-slate-700">
      <div class="h-full rounded-full" :class="tone.bar" :style="{ width: `${Math.min(100, percent)}%` }" />
    </div>
    <span class="flex shrink-0 gap-3 whitespace-nowrap" :class="tone.text">
      <span class="tabular-nums">{{ Math.round(percent) }} %</span>
      <span>{{ reset }}</span>
    </span>
  </div>
</template>
