<script setup lang="ts">
import { computed } from 'vue'
import { formatTokens } from '../format'
import ContextRing from './ContextRing.vue'

const props = defineProps<{ tokens: number; window: number; compact?: boolean }>()

const percent = computed(() => Math.min(100, Math.round((props.tokens / props.window) * 100)))
const detail = computed(() => ({
  used: formatTokens(props.tokens),
  total: formatTokens(props.window),
  percent: percent.value,
}))
</script>

<!-- Only the ring shows the warning colour: coloured text looked larger than the grey rows. -->
<template>
  <span
    class="inline-flex shrink-0 items-center gap-1.5 text-xs text-slate-400"
    :title="$t('sessions.context', detail)"
  >
    <ContextRing :percent="percent" />
    <!-- Narrow screens (and the compact form) show the percentage only, wider ones the tokens too. -->
    <span v-if="!compact" class="hidden sm:inline">{{ $t('sessions.context', detail) }}</span>
    <span :class="{ 'sm:hidden': !compact }">{{ percent }} %</span>
  </span>
</template>
