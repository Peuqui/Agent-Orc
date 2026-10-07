<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type AgentSession } from '../api'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'
import ConfirmDialog from './ConfirmDialog.vue'

// Empties the agent's context in place (it keeps running, unlike a restart); only between two
// answers, as clearing in the middle of one would throw its work away.
const props = defineProps<{ session: AgentSession; buttonClass: string }>()
const { t } = useI18n()
const toast = useToast()
const { refresh } = useSessions()
const asking = ref(false)

async function clear(): Promise<void> {
  asking.value = false
  try {
    await api.clearContext(props.session.id)
    toast.info(t('clear.done', { name: sessionName(props.session) }))
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <button
    :class="buttonClass"
    :title="$t(session.busy ? 'clear.busy' : 'clear.title')"
    :aria-label="$t('clear.title')"
    :disabled="session.busy"
    @click="asking = true"
  >
    <AppIcon name="clear" />
  </button>
  <ConfirmDialog
    v-if="asking"
    :title="$t('clear.title')"
    :message="$t('clear.confirm', { name: sessionName(session) })"
    :confirm-label="$t('clear.title')"
    danger
    @confirm="clear"
    @close="asking = false"
  />
</template>
