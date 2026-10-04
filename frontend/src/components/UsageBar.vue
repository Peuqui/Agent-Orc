<script setup lang="ts">
import { computed } from 'vue'
import { usageTone } from '../usage'

const props = defineProps<{ label: string; percent: number; detail: string }>()

const tone = computed(() => usageTone(props.percent))
</script>

<template>
  <div class="flex flex-col gap-1">
    <div class="flex justify-between gap-2 text-xs text-slate-400">
      <span>{{ label }}</span>
      <span :class="tone.text">{{ detail }}</span>
    </div>
    <div class="h-1.5 overflow-hidden rounded-full bg-slate-700">
      <div class="h-full rounded-full" :class="tone.bar" :style="{ width: `${Math.min(100, percent)}%` }" />
    </div>
  </div>
</template>
