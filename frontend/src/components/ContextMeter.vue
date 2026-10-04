<script setup lang="ts">
import { computed } from 'vue'
import { formatTokens } from '../format'
import { usageTone } from '../usage'
import UsageBar from './UsageBar.vue'

const props = defineProps<{ tokens: number; window: number; compact?: boolean }>()

const percent = computed(() => Math.min(100, Math.round((props.tokens / props.window) * 100)))
const detail = computed(() => ({
  used: formatTokens(props.tokens),
  total: formatTokens(props.window),
  percent: percent.value,
}))
</script>

<template>
  <span
    v-if="compact"
    class="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-xs"
    :class="usageTone(percent).text"
    :title="$t('sessions.context', detail)"
  >
    {{ percent }} %
  </span>
  <UsageBar v-else :label="$t('sessions.contextLabel')" :percent="percent" :detail="$t('sessions.context', detail)" />
</template>
