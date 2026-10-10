<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { type AgentSession, type ContextAction } from '../api'
import { sessionName, useSessions } from '../composables/useSessions'
import { useApi } from '../composables/useHostContext'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'
import ConfirmDialog from './ConfirmDialog.vue'

// Empties or shrinks the agent's context in place (it keeps running, unlike a restart); only
// between two answers, as doing it in the middle of one would throw its work away.
const props = defineProps<{
  session: AgentSession
  action: ContextAction
  buttonClass: string
  withLabel?: boolean
}>()
const emit = defineEmits<{ done: [] }>()
const { t } = useI18n()
const toast = useToast()
const api = useApi()
const { refresh } = useSessions()
const asking = ref(false)

async function run(): Promise<void> {
  asking.value = false
  emit('done')
  try {
    await api.changeContext(props.session.id, props.action)
    toast.info(t(`context.${props.action}.done`, { name: sessionName(props.session) }))
  } catch (error) {
    toast.error(error)
  }
  await refresh()
}
</script>

<template>
  <button
    :class="buttonClass"
    :title="$t(session.busy ? 'context.busy' : `context.${action}.title`)"
    :aria-label="$t(`context.${action}.title`)"
    :disabled="session.busy"
    @click="asking = true"
  >
    <AppIcon :name="action" /><span v-if="withLabel">{{ $t(`context.${action}.title`) }}</span>
  </button>
  <ConfirmDialog
    v-if="asking"
    :title="$t(`context.${action}.title`)"
    :message="$t(`context.${action}.confirm`, { name: sessionName(session) })"
    :confirm-label="$t(`context.${action}.title`)"
    :danger="action === 'clear'"
    @confirm="run"
    @close="((asking = false), emit('done'))"
  />
</template>
