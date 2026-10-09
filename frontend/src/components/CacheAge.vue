<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AgentSession } from '../api'
import { useNow } from '../composables/useNow'
import { formatMinutes } from '../format'

// How old the agent's prompt cache is, next to its name: warm (green), shortly before it expires
// (amber, the handover is due), cold (red: the next message reads the whole context in again).
// Compact (a terminal's narrow header) it leaves where a handover stands to the tooltip.
const props = defineProps<{ session: AgentSession; compact?: boolean }>()
const { t } = useI18n()
const now = useNow()

const remaining = computed(() => {
  const cache = props.session.cache
  return cache === null ? null : cache.last_request + cache.window_seconds - now.value
})
const label = computed(() => {
  const cache = props.session.cache
  if (props.session.busy) return t('cache.active')
  return cache === null ? null : formatMinutes(now.value - cache.last_request)
})
const tone = computed(() => {
  const cache = props.session.cache
  if (props.session.busy || cache === null || remaining.value === null) return 'text-slate-400'
  if (remaining.value <= 0) return 'text-red-400'
  return remaining.value <= cache.lead_seconds ? 'text-amber-300' : 'text-emerald-400'
})
const handover = computed(() => {
  const progress = props.session.handover.progress
  return progress === null ? null : t(`cache.handover.${progress}`)
})
const title = computed(() => {
  if (remaining.value === null) return ''
  const state =
    remaining.value > 0
      ? t('cache.expiresIn', { time: formatMinutes(remaining.value) })
      : t('cache.coldFor', { time: formatMinutes(-remaining.value) })
  return handover.value && props.compact ? `${state} · ${handover.value}` : state
})
</script>

<template>
  <span v-if="label" class="flex shrink-0 items-center gap-1 text-xs whitespace-nowrap" :class="tone" :title="title">
    <span aria-hidden="true">●</span>{{ label }}<span v-if="handover && !compact" class="text-slate-400">· {{ handover }}</span>
  </span>
</template>
