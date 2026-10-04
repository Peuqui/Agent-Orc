<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { QuotaWindow } from '../api'
import { useSessions } from '../composables/useSessions'
import UsageBar from './UsageBar.vue'
import UsageMeter from './UsageMeter.vue'

// compact: one line without a card, e.g. in the workspace's header: the bars where there is
// room, small rings otherwise (phones too), whose name and reset show on hover or tap.
defineProps<{ compact?: boolean }>()
const { quotas } = useSessions()
const { t, te, locale } = useI18n()
const MILLISECONDS_PER_SECOND = 1000

function windowLabel(name: string): string {
  return te(`quota.${name}`) ? t(`quota.${name}`) : name
}

function shortLabel(name: string): string {
  return te(`quota.short.${name}`) ? t(`quota.short.${name}`) : name
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
  <!-- One root, so a class from outside (e.g. hidden on phones) applies to the whole panel. -->
  <div>
    <div
      v-for="quota in quotas"
      :key="quota.profile"
      class="flex"
      :class="
        compact
          ? 'items-center rounded-md border border-slate-600 py-1'
          : 'card mb-4 flex-col gap-x-6 gap-y-1 px-4 py-2.5 md:flex-row md:items-center'
      "
      :title="compact ? $t('quota.title', { agent: quota.label }) : undefined"
    >
      <h2 v-if="!compact" class="shrink-0 text-sm font-semibold text-slate-300">
        {{ $t('quota.title', { agent: quota.label }) }}
      </h2>
      <p v-if="!compact && Object.keys(quota.windows).length === 0" class="text-xs text-slate-500">{{ $t('quota.none') }}</p>
      <!-- The bars; in the compact form only in wide windows, rings stand in elsewhere. -->
      <div
        :class="
          compact
            ? 'hidden w-[36rem] grid-cols-2 divide-x divide-slate-600 2xl:grid'
            : 'grid flex-1 gap-x-6 gap-y-1 md:grid-cols-2'
        "
      >
        <UsageBar
          v-for="(usage, name) in quota.windows"
          :key="name"
          :class="{ 'px-3': compact }"
          :label="windowLabel(String(name))"
          :percent="usage.used_percentage"
          :detail="detail(usage)"
        />
      </div>
      <div v-if="compact" class="flex divide-x divide-slate-600 2xl:hidden">
        <UsageMeter
          v-for="(usage, name) in quota.windows"
          :key="name"
          class="px-2"
          :percent="usage.used_percentage"
          :title="`${windowLabel(String(name))}: ${detail(usage)}`"
          :detail="`${shortLabel(String(name))} ${Math.round(usage.used_percentage)} %`"
        />
      </div>
    </div>
  </div>
</template>
