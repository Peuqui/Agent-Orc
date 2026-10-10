<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { QuotaWindow } from '../api'
import { useSessions } from '../composables/useSessions'
import { formatMoment } from '../format'
import UsageBar from './UsageBar.vue'
import UsageMeter from './UsageMeter.vue'

// The usage limits of the account in one line without a card, for every page: the bars where the
// panel has room (a container query on the room it gets, not the window), small rings otherwise
// (phones too), whose name and reset show on hover or tap. Nothing until an agent has reported.
const { quotas } = useSessions()
const reported = computed(() => quotas.value.filter((quota) => Object.keys(quota.windows).length > 0))
const { t, te, locale } = useI18n()
const MILLISECONDS_PER_SECOND = 1000

function windowLabel(name: string): string {
  return te(`quota.${name}`) ? t(`quota.${name}`) : name
}

function shortLabel(name: string): string {
  return te(`quota.short.${name}`) ? t(`quota.short.${name}`) : name
}

function resetText(window: QuotaWindow): string {
  const when = formatMoment(new Date(window.resets_at * MILLISECONDS_PER_SECOND), locale.value)
  return t('quota.reset', { when })
}

function detail(window: QuotaWindow): string {
  const when = formatMoment(new Date(window.resets_at * MILLISECONDS_PER_SECOND), locale.value)
  return t('quota.detail', { percent: Math.round(window.used_percentage), when })
}
</script>

<template>
  <!-- One root, so a class from outside applies to the whole panel; it is also the container
       the form measures. -->
  <div class="@container">
    <div
      v-for="quota in reported"
      :key="quota.profile"
      class="mx-auto flex w-fit max-w-[38rem] items-center rounded-md border border-slate-600 py-1"
      :title="$t('quota.title', { agent: quota.label })"
    >
      <!-- The bars, in wide places; rings stand in elsewhere. -->
      <div class="hidden min-w-0 divide-x divide-slate-600 @[34rem]:flex">
        <UsageBar
          v-for="(usage, name) in quota.windows"
          :key="name"
          class="px-3"
          :label="windowLabel(String(name))"
          :percent="usage.used_percentage"
          :reset="resetText(usage)"
        />
      </div>
      <div class="flex divide-x divide-slate-600 @[34rem]:hidden">
        <UsageMeter
          v-for="(usage, name) in quota.windows"
          :key="name"
          class="px-2"
          room-of="container"
          :percent="usage.used_percentage"
          :title="`${windowLabel(String(name))}: ${detail(usage)}`"
          :detail="`${shortLabel(String(name))} ${Math.round(usage.used_percentage)} %`"
        />
      </div>
    </div>
  </div>
</template>
