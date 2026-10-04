<script setup lang="ts">
import ContextRing from './ContextRing.vue'

// A usage (context window, account limit) as a small ring with its percentage; from sm on a
// longer text replaces the bare percentage where there is one. The text stays grey: only the
// ring carries the warning colour (coloured text looked larger than the grey rows).
defineProps<{
  /** 0 to 100. */
  percent: number
  /** Shown on hover or tap. */
  title: string
  detail?: string
}>()
</script>

<template>
  <span class="inline-flex shrink-0 items-center gap-1.5 text-xs whitespace-nowrap text-slate-400" :title="title">
    <ContextRing :percent="percent" />
    <span v-if="detail" class="hidden sm:inline">{{ detail }}</span>
    <span :class="{ 'sm:hidden': detail }">{{ Math.round(percent) }} %</span>
  </span>
</template>
