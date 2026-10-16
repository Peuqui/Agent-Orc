<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { formatDay } from '../format'

// The day over its messages, as a messenger shows it, so the messages need only their time.
defineProps<{ date: Date }>()
const { locale, t } = useI18n()
</script>

<template>
  <div class="relative my-2 flex justify-center">
    <span class="rounded-full bg-slate-900 px-3 py-0.5 text-xs text-slate-400">
      {{ formatDay(date, locale, { today: t('peers.today'), yesterday: t('peers.yesterday') }) }}
    </span>
  </div>
</template>
