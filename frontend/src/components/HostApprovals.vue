<script setup lang="ts">
import { computed, onBeforeUnmount, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { apiFor, type AgentSession, currentHost } from '../api'
import { useApprovalFolds } from '../composables/useApprovalFolds'
import { useBannerRoot } from '../composables/useBannerRoot'
import { useDismiss } from '../composables/useDismiss'
import { provideHost } from '../composables/useHostContext'
import { useApprovalChanges } from '../composables/useApprovalChanges'
import { useHostLinks } from '../composables/useHostLinks'
import { sessionName, useSessions } from '../composables/useSessions'
import { isShownAgent } from '../composables/useShownAgents'
import { useToast } from '../composables/useToast'
import { agentRoute } from '../composables/useWorkspaceTab'
import ApprovalRequests from './ApprovalRequests.vue'

// The requests waiting at one machine's agents, for the banner at the top of every page. A request
// is pushed here as soon as the machine reports it; a click on the agent's name goes to its page
// on that machine. × on a card, a press beside the banner or Escape folds the open cards to red
// pills in the header (BannerChips), as the holds fold; a tap on a pill opens its card again, and a
// new request of the agent shows open by itself. Folding sends nothing: the agent keeps waiting.
const props = defineProps<{ host: string | null }>()
provideHost(props.host)
const route = useRoute()
const toast = useToast()
const { go } = useHostLinks(props.host)
const { sessions, refresh } = useSessions(props.host)
useApprovalChanges(() => void refresh(), props.host)
const { isFolded, fold, publish, withdraw } = useApprovalFolds()

const agentPage = (id: string): string => `/terminal/${encodeURIComponent(id)}`
const inView = (id: string): boolean =>
  (props.host === currentHost && route.path === agentPage(id)) || isShownAgent(props.host, id)
const waiting = computed(() =>
  sessions.value.filter((session) => session.approvals.length > 0 && !inView(session.id)),
)

const approvalIds = (session: AgentSession): string[] => session.approvals.map((approval) => approval.id)
const open = computed(() => waiting.value.filter((session) => !isFolded(approvalIds(session))))

const hostKey = props.host ?? ''
watchEffect(() =>
  publish(
    hostKey,
    waiting.value.map((session) => ({
      key: `${hostKey}|${session.id}`,
      name: sessionName(session),
      hostName: props.host,
      approvalIds: approvalIds(session),
    })),
  ),
)
onBeforeUnmount(() => withdraw(hostKey))

useDismiss(
  useBannerRoot(),
  () => open.value.length > 0,
  () => {
    for (const session of open.value) fold(approvalIds(session), true)
  },
)

async function goTo(id: string): Promise<void> {
  try {
    await go(agentRoute(await apiFor(props.host).workspaces(), id))
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <ApprovalRequests
    v-for="session in open"
    :key="session.id"
    :session="session"
    named
    :host-name="host"
    class="pointer-events-auto w-full max-w-xl rounded-lg bg-page shadow-xl"
    @open="goTo(session.id)"
    @fold="fold(approvalIds(session), true)"
  />
</template>
