import { ref } from 'vue'

export interface AgentProfile {
  name: string
  label: string
  /** Selectable reasoning effort; empty if the agent has none. */
  effort_levels: string[]
  /** The agent offers ultracode (workflow orchestration) next to the effort. */
  ultracode: boolean
}

export interface AgentSession {
  id: string
  profile: string
  path: string
  running: boolean
  exit_status: number | null
  created: number
  /** Reported by the agent itself (Claude: via `agent-orc statusline`); null until it reports. */
  model: string | null
  effort: string | null
  /** The agent is working on an answer (reported by its hooks). */
  busy: boolean
  /** Stored for the folder; the agent reads it at start. */
  ultracode: boolean
  /** A reasoning change waits until the current answer is finished. */
  effort_pending: boolean
  pending_effort: string | null
  pending_ultracode: boolean | null
  /** Occupied context window in tokens; null when unknown. */
  context_tokens: number | null
  context_window: number | null
}

/** One usage window of an account, e.g. five hours or a week; resets_at in Unix seconds. */
export interface QuotaWindow {
  used_percentage: number
  resets_at: number
}

/** Usage limits of an agent profile; windows stay empty until the agent has reported them. */
export interface AgentQuota {
  profile: string
  label: string
  windows: Record<string, QuotaWindow>
}

/** Reasoning of an agent, stored per folder: effort (null: the agent's default) and ultracode. */
export interface Reasoning {
  effort: string | null
  ultracode: boolean
}

/** Where Whisper transcribes: the GPU is near instant, the CPU slower but always there. */
export type DictationDevice = 'cuda' | 'cpu'

export interface FileEntry {
  name: string
  path: string
  is_dir: boolean
  size: number
  modified: number
}

export interface ScopeState {
  root: string
  base_dir: string
  seconds_unlocked: number
  unlock_minutes: number
}

export interface TrashEntry {
  id: string
  original_path: string
  deleted_at: string
  is_dir: boolean
}

export interface TextFile {
  content: string
  /** Opaque version token; compare and send back unchanged. */
  version: string
}

export type Modifier = 'ctrl' | 'alt'

export interface TerminalKey {
  label: string
  send: string | null
  modifier: Modifier | null
}

export interface TerminalSettings {
  keys: TerminalKey[][]
  submit_delay_ms: number
}

export interface Conversation {
  id: string
  title: string
  modified: number
  size: number
  /** Written to in the last minutes: probably still open elsewhere, e.g. in VS Code. */
  recently_active: boolean
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    /** From the Retry-After header of a login lockout. */
    readonly retryAfterSeconds: number | null,
  ) {
    super(message)
  }
}

/** null until the first request tells whether the login cookie is valid. */
export const authenticated = ref<boolean | null>(null)

/** The server runs a different build than this page: it needs a reload. */
export const newVersion = ref(false)

const NO_CONTENT = 204
// Sent by the server with the id of its installed build (agent_orc.api.BUILD_ID_HEADER).
const BUILD_ID_HEADER = 'X-Build-Id'
export const NETWORK_ERROR = 'NetworkError'

async function request<T>(
  method: string,
  path: string,
  /** body is sent as JSON, upload (e.g. recorded audio) as it is. */
  options: { body?: unknown; upload?: Blob; query?: Record<string, string> } = {},
): Promise<T> {
  // Relative to the page, so the app also works under a reverse-proxy sub-path.
  const url = new URL(`api/${path}`, document.baseURI)
  for (const [key, value] of Object.entries(options.query ?? {})) {
    url.searchParams.set(key, value)
  }
  let headers: Record<string, string> = {}
  let body: BodyInit | undefined
  if (options.upload !== undefined) {
    headers = { 'Content-Type': options.upload.type }
    body = options.upload
  } else if (options.body !== undefined) {
    headers = { 'Content-Type': 'application/json' }
    body = JSON.stringify(options.body)
  }
  let response: Response
  try {
    response = await fetch(url, { method, credentials: 'same-origin', headers, body })
  } catch (error) {
    // fetch only rejects when no HTTP response arrived at all (server down, network gone).
    throw new ApiError(0, NETWORK_ERROR, String(error), null)
  }
  checkBuild(response)
  if (response.status === 401 && path !== 'login' && path !== 'scope/unlock') {
    authenticated.value = false
  }
  if (!response.ok) {
    const data = await response.json()
    // Agent-Orc errors carry {error, detail}; FastAPI's own errors only {detail}.
    const code: string = data.error ?? `http${response.status}`
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    const retryAfter = response.headers.get('Retry-After')
    throw new ApiError(response.status, code, detail, retryAfter === null ? null : Number(retryAfter))
  }
  return response.status === NO_CONTENT ? (undefined as T) : ((await response.json()) as T)
}

function checkBuild(response: Response): void {
  const serverBuild = response.headers.get(BUILD_ID_HEADER)
  // The Vite dev server's page is no installed build, so there is nothing to compare.
  if (!import.meta.env.DEV && serverBuild !== null && serverBuild !== __BUILD_ID__) {
    newVersion.value = true
  }
}

export const api = {
  login: (password: string) => request<void>('POST', 'login', { body: { password } }),
  logout: () => request<void>('POST', 'logout'),
  me: () => request<{ authenticated: boolean }>('GET', 'me'),

  scope: () => request<ScopeState>('GET', 'scope'),
  unlock: (password: string) => request<ScopeState>('POST', 'scope/unlock', { body: { password } }),
  lock: () => request<ScopeState>('POST', 'scope/lock'),

  agents: () => request<AgentProfile[]>('GET', 'agents'),
  terminalSettings: () => request<TerminalSettings>('GET', 'terminal'),
  sessions: () => request<AgentSession[]>('GET', 'sessions'),
  /**
   * reasoning is stored for the folder; conversation resumes that earlier conversation,
   * resume the last one.
   */
  startSession: (
    profile: string,
    path: string,
    resume: boolean,
    reasoning: Reasoning,
    conversation: string | null = null,
  ) =>
    request<AgentSession>('POST', 'sessions', {
      body: { profile, path, resume, ...reasoning, conversation },
    }),
  conversations: (profile: string, path: string) =>
    request<Conversation[]>('GET', 'conversations', { query: { profile, path } }),
  folderReasoning: (profile: string, path: string) =>
    request<Reasoning>('GET', 'effort', { query: { profile, path } }),
  /**
   * Stores the folder's reasoning and resumes the agent (it reads it only at start).
   * Without `immediately` a busy agent first finishes its answer; then applied is false.
   */
  changeReasoning: (sessionId: string, reasoning: Reasoning, immediately: boolean) =>
    request<{ applied: boolean }>('POST', `sessions/${encodeURIComponent(sessionId)}/effort`, {
      body: { ...reasoning, immediately },
    }),
  cancelEffortChange: (sessionId: string) =>
    request<void>('DELETE', `sessions/${encodeURIComponent(sessionId)}/effort`),
  stopSession: (id: string) => request<void>('DELETE', `sessions/${encodeURIComponent(id)}`),
  /** The terminal as plain text, for selecting and copying. */
  sessionText: (id: string) =>
    request<{ text: string }>('GET', `sessions/${encodeURIComponent(id)}/text`),

  quota: () => request<AgentQuota[]>('GET', 'quota'),
  /** Folders of the agent cards in the order the user arranged them (kept on the server). */
  cardOrder: () => request<string[]>('GET', 'card-order'),
  arrangeCards: (folders: string[]) => request<void>('PUT', 'card-order', { body: { folders } }),

  dictationSettings: () => request<{ language: string; whisper: boolean }>('GET', 'dictation'),
  /** Transcribe recorded speech on the chosen device; never switches device by itself. */
  dictate: (audio: Blob, device: DictationDevice) =>
    request<{ text: string }>('POST', 'dictation', { upload: audio, query: { device } }),

  listFiles: (path: string) => request<FileEntry[]>('GET', 'files', { query: { path } }),
  createFolder: (parent: string, name: string) =>
    request<{ path: string }>('POST', 'files/folder', { body: { parent, name } }),
  rename: (path: string, newName: string) =>
    request<{ path: string }>('POST', 'files/rename', { body: { path, new_name: newName } }),
  readFile: (path: string) => request<TextFile>('GET', 'files/content', { query: { path } }),
  writeFile: (path: string, content: string, expectedVersion: string | null) =>
    request<{ version: string }>('PUT', 'files/content', {
      body: { path, content, expected_version: expectedVersion },
    }),
  moveToTrash: (path: string) => request<TrashEntry>('POST', 'files/trash', { body: { path } }),

  listTrash: () => request<TrashEntry[]>('GET', 'trash'),
  restore: (id: string) => request<{ path: string }>('POST', 'trash/restore', { body: { id } }),
  deleteFromTrash: (id: string) => request<void>('DELETE', `trash/${encodeURIComponent(id)}`),
  emptyTrash: () => request<void>('DELETE', 'trash'),
}

/** WebSocket URL of a session's terminal, relative to the page like all API calls. */
export function terminalUrl(sessionId: string): string {
  const url = new URL(`api/sessions/${encodeURIComponent(sessionId)}/terminal`, document.baseURI)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}
