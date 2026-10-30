<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { apiFor } from '../api'
import { provideHost } from '../composables/useHostContext'
import { useApprovalChanges } from '../composables/useApprovalChanges'
import { useHostLinks } from '../composables/useHostLinks'
import { useSessions } from '../composables/useSessions'
import { isShownAgent } from '../composables/useShownAgents'
import { useToast } from '../composables/useToast'
import { agentRoute } from '../composables/useWorkspaceTab'
import ApprovalRequests from './ApprovalRequests.vue'

// The requests waiting at one machine's agents, for the banner at the top of every page. A request
// is pushed here as soon as the machine reports it; a click on the agent's name goes to its page
// on that machine.
const props = defineProps<{ host: string | null }>()
provideHost(props.host)
const route = useRoute()
const toast = useToast()
const { go } = useHostLinks(props.host)
const { sessions, refresh } = useSessions(props.host)
useApprovalChanges(() => void refresh(), props.host)

const agentPage = (id: string): string => `/terminal/${encodeURIComponent(id)}`
const inView = (id: string): boolean =>
  (props.host === null && route.path === agentPage(id)) || isShownAgent(props.host, id)
const waiting = computed(() =>
  sessions.value.filter((session) => session.approvals.length > 0 && !inView(session.id)),
)

async function open(id: string): Promise<void> {
  try {
    await go(agentRoute(await apiFor(props.host).workspaces(), id))
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <ApprovalRequests
    v-for="session in waiting"
    :key="session.id"
    :session="session"
    named
    :host-name="host"
    class="pointer-events-auto w-full max-w-xl rounded-lg bg-page shadow-xl"
    @open="open(session.id)"
  />
</template>
