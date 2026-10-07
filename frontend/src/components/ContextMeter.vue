<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTokenFormat } from '../composables/useTokenFormat'
import UsageMeter from './UsageMeter.vue'

// The agent's context window: the tokens too where there is room, unless compact.
const props = defineProps<{ tokens: number; window: number; compact?: boolean }>()
const { t } = useI18n()
const formatTokens = useTokenFormat()

const percent = computed(() => Math.min(100, Math.round((props.tokens / props.window) * 100)))
const text = computed(() =>
  t('sessions.context', {
    used: formatTokens(props.tokens),
    total: formatTokens(props.window),
    percent: percent.value,
  }),
)
</script>

<template>
  <UsageMeter :percent="percent" :title="text" :detail="compact ? undefined : text" />
</template>
