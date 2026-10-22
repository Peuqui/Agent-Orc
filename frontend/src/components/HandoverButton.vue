<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AgentSession } from '../api'
import { useApi } from '../composables/useHostContext'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'

// Asks the agent for a handover document by hand, however full its context (the ⋮ menu); also
// while it works, as it takes the request in at its next step. Not while it waits for an answer
// to a prompt: the request would answer it.
const props = defineProps<{ session: AgentSession; buttonClass: string }>()
const emit = defineEmits<{ done: [] }>()
const { t } = useI18n()
const toast = useToast()
const api = useApi()
const { refresh } = useSessions()
const waiting = computed(() => props.session.approvals.length > 0)

async function ask(): Promise<void> {
  emit('done')
  try {
    await api.requestHandover(props.session.id)
    toast.info(t('handover.asked', { name: sessionName(props.session) }))
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <button
    :class="buttonClass"
    :title="$t(waiting ? 'handover.waiting' : 'handover.requestHint')"
    :disabled="!session.running || waiting"
    @click="ask"
  >
    <AppIcon name="pencil" />{{ $t('handover.request') }}
  </button>
</template>
