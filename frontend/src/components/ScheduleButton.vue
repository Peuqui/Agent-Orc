<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { type AgentSession } from '../api'
import { sessionName, useSessions } from '../composables/useSessions'
import { useApi } from '../composables/useHostContext'
import { useToast } from '../composables/useToast'
import { formatMoment } from '../format'
import AppIcon from './AppIcon.vue'
import BaseDialog from './BaseDialog.vue'

// Plans a prompt for later, e.g. "run the tests and report" at seven in the morning; it is
// typed in once due and the agent has finished what it is doing then.
const props = defineProps<{ session: AgentSession; buttonClass: string; withLabel?: boolean }>()
const emit = defineEmits<{ done: [] }>()
const { locale, t } = useI18n()
const toast = useToast()
const api = useApi()
const { refresh } = useSessions()
const MILLISECONDS_PER_SECOND = 1000
const DEFAULT_DELAY_MILLISECONDS = 60 * 60 * MILLISECONDS_PER_SECOND

const planning = ref(false)
const text = ref('')
const when = ref('')

/** The value of a datetime-local input: local time, to the minute. */
function localInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function open(): void {
  text.value = ''
  when.value = localInputValue(new Date(Date.now() + DEFAULT_DELAY_MILLISECONDS))
  planning.value = true
}

async function plan(): Promise<void> {
  // datetime-local values carry no zone: Date reads them as local time.
  const at = new Date(when.value)
  try {
    await api.schedulePrompt(props.session.id, text.value.trim(), at.getTime() / MILLISECONDS_PER_SECOND)
    planning.value = false
    toast.info(t('schedule.done', { name: sessionName(props.session), when: formatMoment(at, locale.value) }))
    emit('done')
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <button :class="buttonClass" :title="$t('schedule.title')" :aria-label="$t('schedule.title')" @click="open">
    <AppIcon name="clock" /><span v-if="withLabel">{{ $t('schedule.title') }}</span>
  </button>
  <BaseDialog v-if="planning" :title="$t('schedule.title')" @close="((planning = false), emit('done'))">
    <form class="flex flex-col gap-3" @submit.prevent="plan">
      <textarea v-model="text" rows="4" class="input text-sm" :placeholder="$t('schedule.text')" required />
      <label class="flex flex-col gap-1 text-sm text-slate-300">
        {{ $t('schedule.at') }}
        <input v-model="when" type="datetime-local" class="input" required />
      </label>
      <p class="text-xs text-slate-500">{{ $t('schedule.hint') }}</p>
      <div class="flex gap-2">
        <button type="submit" class="btn-primary flex-1" :disabled="!text.trim() || !when">
          {{ $t('schedule.plan') }}
        </button>
        <button type="button" class="btn" @click="planning = false">{{ $t('common.cancel') }}</button>
      </div>
    </form>
  </BaseDialog>
</template>
