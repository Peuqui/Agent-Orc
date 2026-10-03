<script setup lang="ts">
import { computed } from 'vue'
import { formatTokens } from '../format'

const props = defineProps<{ tokens: number; window: number; compact?: boolean }>()

// From here on a fresh session or /compact is worth considering.
const WARN_PERCENT = 70
const CRITICAL_PERCENT = 90

const percent = computed(() => Math.min(100, Math.round((props.tokens / props.window) * 100)))
const tone = computed(() =>
  percent.value >= CRITICAL_PERCENT
    ? 'bg-red-500 text-red-400'
    : percent.value >= WARN_PERCENT
      ? 'bg-amber-500 text-amber-400'
      : 'bg-slate-400 text-slate-400',
)
</script>

<template>
  <span
    v-if="compact"
    class="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-xs"
    :class="tone.split(' ')[1]"
    :title="$t('sessions.context', { used: formatTokens(tokens), total: formatTokens(window), percent })"
  >
    {{ percent }} %
  </span>
  <div v-else class="flex flex-col gap-1">
    <div class="flex justify-between text-xs text-slate-400">
      <span>{{ $t('sessions.contextLabel') }}</span>
      <span :class="tone.split(' ')[1]">
        {{ $t('sessions.context', { used: formatTokens(tokens), total: formatTokens(window), percent }) }}
      </span>
    </div>
    <div class="h-1.5 overflow-hidden rounded-full bg-slate-700">
      <div class="h-full rounded-full" :class="tone.split(' ')[0]" :style="{ width: `${percent}%` }" />
    </div>
  </div>
</template>
