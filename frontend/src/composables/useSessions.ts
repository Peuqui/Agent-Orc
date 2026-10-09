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

// A folder's agent and its terminal, each by folder.
const sessionByPath = computed(
  () => new Map(sessions.value.filter((s) => !s.terminal).map((s) => [s.path, s])),
)
const terminalByPath = computed(
  () => new Map(sessions.value.filter((s) => s.terminal).map((s) => [s.path, s])),
)
// The profile that opens a plain terminal (">_"); none if the config has no such profile.
const terminalProfile = computed(() => profiles.value.find((profile) => profile.terminal) ?? null)

const TERMINAL_KEY_SUFFIX = '\n>_'

/** How a session is called: its name (the folder's), and for the folder's terminal ">_" after it. */
export function sessionName(session: AgentSession): string {
  return session.terminal ? `${session.name} >_` : session.name
}

/** A card's identity (its place in the user's order): the folder, marked for its terminal or
 * with the suffix of a further agent. */
export function cardKey(session: AgentSession): string {
  if (session.terminal) return `${session.path}${TERMINAL_KEY_SUFFIX}`
  return session.suffix === null ? session.path : `${session.path}\n${session.suffix}`
}

export function useSessions() {
  return {
    sessions,
    profiles,
    quotas,
    sessionByPath,
    terminalByPath,
    terminalProfile,
    refresh,
    startPolling,
    stopPolling,
    loadProfiles,
  }
}
