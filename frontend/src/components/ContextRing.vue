<script setup lang="ts">
import { computed } from 'vue'
import { usageTone } from '../usage'

// Context usage as a small ring that fills clockwise from 0 to 100 % (like Claude Code's,
// but visible from the start).
/** 0 to 100. */
const props = defineProps<{ percent: number }>()

const RADIUS = 7
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

const filled = computed(() => (props.percent / 100) * CIRCUMFERENCE)
</script>

<template>
  <svg class="size-4 shrink-0 -rotate-90" viewBox="0 0 18 18" aria-hidden="true">
    <circle cx="9" cy="9" :r="RADIUS" fill="none" stroke-width="3" class="stroke-slate-700" />
    <circle
      cx="9"
      cy="9"
      :r="RADIUS"
      fill="none"
      stroke-width="3"
      :class="usageTone(percent).ring"
      :stroke-dasharray="`${filled} ${CIRCUMFERENCE}`"
    />
  </svg>
</template>
