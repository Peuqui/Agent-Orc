import { ref } from 'vue'

export interface AgentProfile {
  name: string
  label: string
  /** Selectable reasoning effort; empty if the agent has none. */
  effort_levels: string[]
}

export interface AgentSession {
  id: string
  profile: string
  path: string
  running: boolean
  exit_status: number | null
  created: number
  /** Reported by the agent itself (Claude: via `ai-orc statusline`); null until it reports. */
  model: string | null
  effort: string | null
  /** The agent is working on an answer (reported by its hooks). */
  busy: boolean
  /** An effort change waits until the current answer is finished. */
  effort_pending: boolean
  pending_effort: string | null
  /** Occupied context window in tokens; null when unknown. */
  context_tokens: number | null
  context_window: number | null
}

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

const NO_CONTENT = 204
export const NETWORK_ERROR = 'NetworkError'

async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Record<string, string> } = {},
): Promise<T> {
  // Relative to the page, so the app also works under a reverse-proxy sub-path.
  const url = new URL(`api/${path}`, document.baseURI)
  for (const [key, value] of Object.entries(options.query ?? {})) {
    url.searchParams.set(key, value)
  }
  const hasBody = options.body !== undefined
  let response: Response
  try {
    response = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: hasBody ? { 'Content-Type': 'application/json' } : {},
      body: hasBody ? JSON.stringify(options.body) : undefined,
    })
  } catch (error) {
    // fetch only rejects when no HTTP response arrived at all (server down, network gone).
    throw new ApiError(0, NETWORK_ERROR, String(error), null)
  }
  if (response.status === 401 && path !== 'login' && path !== 'scope/unlock') {
    authenticated.value = false
  }
  if (!response.ok) {
    const data = await response.json()
    // AI-Orc errors carry {error, detail}; FastAPI's own errors only {detail}.
    const code: string = data.error ?? `http${response.status}`
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    const retryAfter = response.headers.get('Retry-After')
    throw new ApiError(response.status, code, detail, retryAfter === null ? null : Number(retryAfter))
  }
  return response.status === NO_CONTENT ? (undefined as T) : ((await response.json()) as T)
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
  /** effort is stored for the folder; null: the agent's own default. */
  startSession: (profile: string, path: string, resume: boolean, effort: string | null) =>
    request<AgentSession>('POST', 'sessions', { body: { profile, path, resume, effort } }),
  folderEffort: (profile: string, path: string) =>
    request<{ effort: string | null }>('GET', 'effort', { query: { profile, path } }),
  /**
   * Stores the folder's effort and resumes the agent (it reads the effort only at start).
   * Without `immediately` a busy agent first finishes its answer; then applied is false.
   */
  changeEffort: (sessionId: string, effort: string | null, immediately: boolean) =>
    request<{ applied: boolean }>('POST', `sessions/${encodeURIComponent(sessionId)}/effort`, {
      body: { effort, immediately },
    }),
  cancelEffortChange: (sessionId: string) =>
    request<void>('DELETE', `sessions/${encodeURIComponent(sessionId)}/effort`),
  stopSession: (id: string) => request<void>('DELETE', `sessions/${encodeURIComponent(id)}`),

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
