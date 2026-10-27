import { computed, ref } from 'vue'
import { apiFor, type AgentProfile, type AgentQuota, type AgentSession } from '../api'
import { COLUMN_TAB } from '../device'
import { useHostContext } from './useHostContext'
import { useToast } from './useToast'

const REFRESH_MILLISECONDS = 3000
// A workspace column is this app again, in an iframe of the page around it. That page polls this
// machine's agents anyway and hands each answer on to its columns, so a column does not poll
// itself: one request every few seconds instead of one per column (each keeps a phone's radio
// awake and makes the server read every agent's state).
const AGENTS_MESSAGE = 'agent-orc-agents'
const APP_ROOT = new URL('./', document.baseURI).href

interface AgentsMessage {
  kind: typeof AGENTS_MESSAGE
  app: string
  sessions: AgentSession[]
  quotas: AgentQuota[]
}

function handToColumns(sessions: AgentSession[], quotas: AgentQuota[]): void {
  const message: AgentsMessage = { kind: AGENTS_MESSAGE, app: APP_ROOT, sessions, quotas }
  for (let index = 0; index < window.frames.length; index++) {
    window.frames[index].postMessage(message, location.origin)
  }
}

/** The agents of one machine (this one's own for host null) with what belongs to them. */
function createStore(host: string | null) {
  const hostApi = apiFor(host)
  const sessions = ref<AgentSession[]>([])
  const profiles = ref<AgentProfile[]>([])
  const quotas = ref<AgentQuota[]>([])
  let timer: number | undefined

  async function refresh(): Promise<void> {
    try {
      // The usage limits belong to the account, which this machine's own app reports.
      const [currentSessions, currentQuotas] = await Promise.all([
        hostApi.sessions(),
        host === null ? hostApi.quota() : quotas.value,
      ])
      sessions.value = currentSessions
      quotas.value = currentQuotas
      if (host === null) handToColumns(currentSessions, currentQuotas)
    } catch (error) {
      useToast().error(error)
    }
  }

  /** What the page around a column handed on (see AGENTS_MESSAGE). */
  function takeFromPage(event: MessageEvent<AgentsMessage>): void {
    if (event.source !== window.parent || event.origin !== location.origin) return
    if (event.data?.kind !== AGENTS_MESSAGE || event.data.app !== APP_ROOT) return
    sessions.value = event.data.sessions
    quotas.value = event.data.quotas
  }

  /** Poll while the app is visible; a backgrounded phone app should not keep polling. A column of
   * the workspace takes what its page polls. */
  function startPolling(): void {
    stopPolling()
    void refresh()
    if (host === null && COLUMN_TAB !== null) {
      window.addEventListener('message', takeFromPage)
      return
    }
    timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh()
    }, REFRESH_MILLISECONDS)
  }

  function stopPolling(): void {
    window.clearInterval(timer)
    window.removeEventListener('message', takeFromPage)
  }

  async function loadProfiles(): Promise<void> {
    profiles.value = await hostApi.agents()
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

const stores = new Map<string | null, ReturnType<typeof createStore>>()

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

/** The agents of the machine of the component's surroundings (see useHostContext), or of `host`. */
export function useSessions(host: string | null = useHostContext()) {
  let store = stores.get(host)
  if (store === undefined) {
    store = createStore(host)
    stores.set(host, store)
  }
  return store
}
