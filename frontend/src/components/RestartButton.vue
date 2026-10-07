<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type AgentChoice, type AgentSession } from '../api'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'
import ConfirmDialog from './ConfirmDialog.vue'
import ModelDialog from './ModelDialog.vue'

// Restarts the agent with its conversation resumed, e.g. when it hangs or should read changed
// settings; asked first, as it ends a running answer and the agent's background tasks.
// With `changeModel` it asks for another model instead: an agent that can switch in place does
// so (a busy one after its answer), any other is restarted with the model.
const props = defineProps<{
  session: AgentSession
  buttonClass: string
  withLabel?: boolean
  changeModel?: boolean
}>()
const { t } = useI18n()
const toast = useToast()
const { profiles, refresh } = useSessions()
const asking = ref(false)

// An agent that offers models but has none stored cannot be resumed without choosing one.
const needsModel = computed(
  () => props.session.chosen_model === null && profile.value?.models,
)

const profile = computed(() => profiles.value.find((p) => p.name === props.session.profile))
const askModel = computed(() => props.changeModel || needsModel.value)
const buttonLabel = computed(() => t(props.changeModel ? 'restart.modelTitle' : 'restart.title'))
const modelMessage = computed(() => {
  const name = sessionName(props.session)
  if (!props.changeModel) return t('restart.chooseModel', { name })
  if (profile.value?.model_live) return t('restart.changeModelLive', { name })
  return t(props.session.busy ? 'restart.changeModelBusy' : 'restart.changeModel', { name })
})

async function restart(choice: AgentChoice | null): Promise<void> {
  asking.value = false
  const model = choice?.model ?? null
  try {
    if (choice !== null && choice.profile !== props.session.profile) {
      await api.changeProfile(props.session.id, choice)
      const agent = profiles.value.find((p) => p.name === choice.profile)?.label ?? choice.profile
      toast.info(t('restart.profileChanged', { name: sessionName(props.session), agent }))
    } else if (props.changeModel && model !== null) {
      const result = await api.changeModel(props.session.id, model, choice?.effort ?? null)
      const done = result.applied ? 'restart.modelChanged' : 'restart.modelScheduled'
      toast.info(t(done, { name: sessionName(props.session), model }))
    } else {
      await api.restartSession(props.session.id, model, choice?.effort ?? null)
      toast.info(t('restart.done', { name: sessionName(props.session) }))
    }
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <button :class="buttonClass" :title="buttonLabel" :aria-label="buttonLabel" @click="asking = true">
    <AppIcon :name="changeModel ? 'model' : 'restart'" /><span v-if="withLabel">{{ buttonLabel }}</span>
  </button>
  <ModelDialog
    v-if="asking && askModel"
    :title="buttonLabel"
    :message="modelMessage"
    :confirm-label="buttonLabel"
    :profile="session.profile"
    :current="session.chosen_model"
    :current-effort="session.effort"
    :choose-profile="changeModel"
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
