<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { type ScheduledPrompt } from '../api'
import { useSessions } from '../composables/useSessions'
import { useApi } from '../composables/useHostContext'
import { useToast } from '../composables/useToast'
import { formatMoment } from '../format'
import AppIcon from './AppIcon.vue'

// What an agent has planned: the user's own prompts and the resume after a usage limit.
defineProps<{ prompts: ScheduledPrompt[] }>()
const { locale } = useI18n()
const toast = useToast()
const api = useApi()
const { refresh } = useSessions()
const MILLISECONDS_PER_SECOND = 1000

function moment(prompt: ScheduledPrompt): Date {
  return new Date(prompt.at * MILLISECONDS_PER_SECOND)
}

async function cancel(prompt: ScheduledPrompt): Promise<void> {
  try {
    await api.cancelScheduled(prompt.id)
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <ul v-if="prompts.length" class="flex flex-col gap-1">
    <li
      v-for="prompt in prompts"
      :key="prompt.id"
      class="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm"
      :class="prompt.reason === 'limit' ? 'border-highlight-700 bg-highlight-950/40 text-highlight-200' : 'border-line text-soft'"
    >
      <AppIcon name="clock" class="shrink-0" />
      <span class="shrink-0 font-medium">
        {{
          moment(prompt) <= new Date()
            ? $t('schedule.due')
            : formatMoment(moment(prompt), locale)
        }}
      </span>
      <span class="min-w-0 flex-1 truncate" :title="prompt.text">
        {{ prompt.reason === 'limit' ? $t('schedule.limit') : prompt.text }}
      </span>
      <button
        class="shrink-0 px-1 text-muted hover:text-main"
        :aria-label="$t('schedule.cancel')"
        :title="$t('schedule.cancel')"
        @click="cancel(prompt)"
      >
        ×
      </button>
    </li>
  </ul>
</template>
