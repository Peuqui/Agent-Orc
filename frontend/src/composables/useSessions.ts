import { computed, ref } from 'vue'
import { api, type AgentProfile, type AgentQuota, type AgentSession } from '../api'
import { useToast } from './useToast'

const REFRESH_MILLISECONDS = 3000

const sessions = ref<AgentSession[]>([])
const profiles = ref<AgentProfile[]>([])
const quotas = ref<AgentQuota[]>([])
let timer: number | undefined

async function refresh(): Promise<void> {
  try {
    const [currentSessions, currentQuotas] = await Promise.all([api.sessions(), api.quota()])
    sessions.value = currentSessions
    quotas.value = currentQuotas
  } catch (error) {
    useToast().error(error)
  }
}

/** Poll while the app is visible; a backgrounded phone app should not keep polling. */
function startPolling(): void {
  stopPolling()
  void refresh()
  timer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void refresh()
  }, REFRESH_MILLISECONDS)
}

function stopPolling(): void {
  window.clearInterval(timer)
}

async function loadProfiles(): Promise<void> {
  profiles.value = await api.agents()
}

const sessionByPath = computed(
  () => new Map(sessions.value.map((session) => [session.path, session])),
)

export function useSessions() {
  return {
    sessions,
    profiles,
    quotas,
    sessionByPath,
    refresh,
    startPolling,
    stopPolling,
    loadProfiles,
  }
}
