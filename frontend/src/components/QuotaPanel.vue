<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { QuotaWindow } from '../api'
import { useSessions } from '../composables/useSessions'
import UsageBar from './UsageBar.vue'

const { quotas } = useSessions()
const { t, te, locale } = useI18n()
const MILLISECONDS_PER_SECOND = 1000

function windowLabel(name: string): string {
  return te(`quota.${name}`) ? t(`quota.${name}`) : name
}

function detail(window: QuotaWindow): string {
  const reset = new Date(window.resets_at * MILLISECONDS_PER_SECOND)
  const sameDay = reset.toDateString() === new Date().toDateString()
  const when = reset.toLocaleString(
    locale.value,
    sameDay ? { timeStyle: 'short' } : { weekday: 'short', hour: '2-digit', minute: '2-digit' },
  )
  return t('quota.detail', { percent: Math.round(window.used_percentage), when })
}
</script>

<template>
  <div v-for="quota in quotas" :key="quota.profile" class="card mb-4 flex flex-col gap-2 p-4">
    <h2 class="text-sm font-semibold text-slate-300">{{ $t('quota.title', { agent: quota.label }) }}</h2>
    <p v-if="Object.keys(quota.windows).length === 0" class="text-xs text-slate-500">{{ $t('quota.none') }}</p>
    <UsageBar
      v-for="(usage, name) in quota.windows"
      :key="name"
      :label="windowLabel(String(name))"
      :percent="usage.used_percentage"
      :detail="detail(usage)"
    />
  </div>
</template>
