<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessions } from '../composables/useSessions'
import { shownAgents } from '../composables/useShownAgents'
import ApprovalRequests from './ApprovalRequests.vue'

// A request of an agent asks at the top of every page, whatever workspace is open, with the
// agent's name; a click on the name goes to that agent. Not for an agent in view: on its own page
// and in the columns of the open workspace the request shows at the input. Inside the workspace's
// iframes it would repeat once per column, so only the outermost page shows it.
const embedded = window.self !== window.top
const route = useRoute()
const router = useRouter()
const { sessions } = useSessions()

const agentPage = (id: string): string => `/terminal/${encodeURIComponent(id)}`
const waiting = computed(() =>
  sessions.value.filter(
    (session) =>
      session.approvals.length > 0 &&
      route.path !== agentPage(session.id) &&
      !shownAgents.value.includes(session.id),
  ),
)
</script>

<template>
  <div
    v-if="!embedded && waiting.length"
    class="fixed inset-x-0 top-0 z-50 flex flex-col items-center gap-2 p-2"
    aria-live="assertive"
  >
    <ApprovalRequests
      v-for="session in waiting"
      :key="session.id"
      :session="session"
      named
      class="w-full max-w-xl rounded-lg bg-slate-900 shadow-xl"
      @open="router.push(agentPage(session.id))"
    />
  </div>
</template>
