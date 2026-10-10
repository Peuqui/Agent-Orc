<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api, rootAddress, type AgentSession } from '../api'
import { useHosts } from '../composables/useHosts'
import { sessionName } from '../composables/useSessions'
import { errorText } from '../composables/useToast'
import { hostPath } from '../hostPaths'
import ContextMeter from './ContextMeter.vue'

// The agents of the other machines, below this machine's own: what they do, and a way in to each.
// Changing them is done in the machine's own app (a click opens it), which is the same app.
const REFRESH_MILLISECONDS = 3000

const { state, refresh } = useHosts()
// Per machine its agents, or why they could not be read.
const agents = ref<Record<string, AgentSession[] | { error: string }>>({})
let timer: number | undefined

async function update(): Promise<void> {
  await refresh()
  for (const host of state.value?.hosts ?? []) {
    if (!host.online) continue
    try {
      agents.value[host.name] = (await api.hostSessions(host.name)).filter((session) => !session.terminal)
    } catch (error) {
      agents.value[host.name] = { error: errorText(error) }
    }
  }
}

onMounted(() => {
  void update()
  timer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void update()
  }, REFRESH_MILLISECONDS)
})
onBeforeUnmount(() => window.clearInterval(timer))

function address(host: string, route: string): string {
  return `${hostPath(new URL(rootAddress()).pathname, host)}#${route}`
}

function list(host: string): AgentSession[] | null {
  const found = agents.value[host]
  return Array.isArray(found) ? found : null
}

function problem(host: string): string | null {
  const found = agents.value[host]
  return found && !Array.isArray(found) ? found.error : null
}
</script>

<template>
  <section v-for="host in state?.hosts ?? []" :key="host.name" class="mt-6">
    <div class="mb-2 flex items-center gap-2">
      <h2 class="text-sm font-semibold text-amber-400">{{ host.name }}</h2>
      <span class="text-xs" :class="host.online ? 'text-emerald-400' : 'text-slate-500'">
        ● {{ host.online ? $t('hosts.online') : $t('hosts.offlineShort') }}
      </span>
      <a v-if="host.online" :href="address(host.name, '/sessions')" class="btn-secondary btn-small ml-auto">
        {{ $t('hosts.open') }}
      </a>
    </div>
    <p v-if="!host.online" class="card p-4 text-sm text-slate-400">{{ $t('hosts.unreachable') }}</p>
    <p v-else-if="problem(host.name)" class="card border-red-700 p-4 text-sm text-red-300">{{ problem(host.name) }}</p>
    <p v-else-if="list(host.name)?.length === 0" class="card p-4 text-sm text-slate-400">{{ $t('sessions.empty') }}</p>
    <ul v-else class="grid grid-cols-[repeat(auto-fill,minmax(min(24rem,100%),1fr))] gap-3">
      <li v-for="session in list(host.name) ?? []" :key="session.id" class="card flex flex-col gap-2 px-4 py-3">
        <div class="flex items-center gap-2">
          <a :href="address(host.name, `/terminal/${session.id}`)" class="min-w-0 flex-1 truncate font-medium text-amber-400">
            {{ sessionName(session) }}
          </a>
          <span v-if="session.running && session.busy" class="text-xs text-amber-400">{{ $t('sessions.working') }}</span>
          <span v-else-if="!session.running" class="text-xs text-slate-500">{{ $t('sessions.ended') }}</span>
          <span v-else class="text-xs text-emerald-400">{{ $t('peers.state.idle') }}</span>
        </div>
        <div class="flex items-center gap-3 text-xs text-slate-400">
          <span v-if="session.model">{{ session.model }}</span>
          <span v-if="session.effort">{{ session.effort }}</span>
          <ContextMeter
            v-if="session.context_tokens != null && session.context_window != null"
            :tokens="session.context_tokens"
            :window="session.context_window"
            compact
            class="ml-auto w-24"
          />
        </div>
      </li>
    </ul>
  </section>
</template>
