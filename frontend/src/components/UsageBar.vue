<script setup lang="ts">
import { computed } from 'vue'
import { usageTone } from '../usage'

const props = defineProps<{ label: string; percent: number; detail: string }>()

const tone = computed(() => usageTone(props.percent))
</script>

<template>
  <div class="flex items-center gap-2 text-xs text-slate-400">
    <!-- Fixed widths, so bars stacked in one card line up. -->
    <span class="w-16 shrink-0">{{ label }}</span>
    <div class="h-1.5 min-w-12 flex-1 overflow-hidden rounded-full bg-slate-700">
      <div class="h-full rounded-full" :class="tone.bar" :style="{ width: `${Math.min(100, percent)}%` }" />
    </div>
    <span class="w-36 min-w-0 shrink truncate text-right" :class="tone.text">{{ detail }}</span>
  </div>
</template>
