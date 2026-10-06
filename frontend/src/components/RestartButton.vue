<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type AgentSession } from '../api'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'
import ConfirmDialog from './ConfirmDialog.vue'
import ModelDialog from './ModelDialog.vue'

// Restarts the agent with its conversation resumed, e.g. when it hangs or should read changed
// settings; asked first, as it ends a running answer and the agent's background tasks.
const props = defineProps<{ session: AgentSession; buttonClass: string; withLabel?: boolean }>()
const { t } = useI18n()
const toast = useToast()
const { profiles, refresh } = useSessions()
const asking = ref(false)

// An agent that offers models but has none stored cannot be resumed without choosing one.
const needsModel = computed(
  () => props.session.chosen_model === null && profiles.value.find((p) => p.name === props.session.profile)?.models,
)

async function restart(model: string | null): Promise<void> {
  asking.value = false
  try {
    await api.restartSession(props.session.id, model)
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
  <ModelDialog
    v-if="asking && needsModel"
    :title="$t('restart.title')"
    :message="$t('restart.chooseModel', { name: sessionName(session) })"
    :confirm-label="$t('restart.title')"
    :profile="session.profile"
    @choose="restart"
    @close="asking = false"
  />
  <ConfirmDialog
    v-else-if="asking"
    :title="$t('restart.title')"
    :message="$t(session.busy ? 'restart.confirmBusy' : 'restart.confirm', { name: sessionName(session) })"
    :confirm-label="$t('restart.title')"
    :danger="session.busy"
    @confirm="restart(null)"
    @close="asking = false"
  />
</template>
