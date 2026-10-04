<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type AgentSession } from '../api'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'
import ConfirmDialog from './ConfirmDialog.vue'

// Restarts the agent with its conversation resumed, e.g. when it hangs or should read changed
// settings; asked first, as it ends a running answer and the agent's background tasks.
const props = defineProps<{ session: AgentSession; buttonClass: string; withLabel?: boolean }>()
const { t } = useI18n()
const toast = useToast()
const { refresh } = useSessions()
const asking = ref(false)

async function restart(): Promise<void> {
  asking.value = false
  try {
    await api.restartSession(props.session.id)
    toast.info(t('restart.done', { name: sessionName(props.session) }))
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <button :class="buttonClass" :title="$t('restart.title')" :aria-label="$t('restart.title')" @click="asking = true">
    <AppIcon name="restart" /><span v-if="withLabel">{{ $t('restart.title') }}</span>
  </button>
  <ConfirmDialog
    v-if="asking"
    :title="$t('restart.title')"
    :message="$t(session.busy ? 'restart.confirmBusy' : 'restart.confirm', { name: sessionName(session) })"
    :confirm-label="$t('restart.title')"
    :danger="session.busy"
    @confirm="restart"
    @close="asking = false"
  />
</template>
