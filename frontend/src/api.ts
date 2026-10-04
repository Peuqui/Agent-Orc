import { ref } from 'vue'

export interface AgentProfile {
  name: string
  label: string
  /** Selectable reasoning effort; empty if the agent has none. */
  effort_levels: string[]
  /** The agent offers ultracode (workflow orchestration) next to the effort. */
  ultracode: boolean
  /** Switches its reasoning in place, without a restart (Claude: /effort). */
  effort_live: boolean
  /** Permission modes a session may start in; empty if the agent has none. */
  permission_modes: string[]
}

/** A file the agent changed (git working tree against the last commit); status as git puts it. */
export interface FileChange {
  path: string
  /** "M", "A", "D", "R", "??" (new, untracked), ... */
  status: string
}

export interface FileDiff {
  text: string
  /** Cut at the server's limit. */
  truncated: boolean
}

/** A text the user keeps for prompts used again and again. */
export interface PromptTemplate {
  label: string
  text: string
}

/** Claude's token consumption of one day, project and model. */
export interface ConsumptionRow {
  /** YYYY-MM-DD, local time. */
  day: string
  /** The folder the conversation ran in. */
  project: string
  model: string
  input: number
  cache_write: number
  cache_read: number
  output: number
  /** Answers. */
  messages: number
}

/** A permission request of an agent, waiting for the user (also asked in its terminal). */
export interface Approval {
  id: string
  tool: string
  /** What the tool would do: the command, the file, ... */
  subject: string
  description: string | null
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
  /** Permission mode the folder's sessions start in; null for agents started before Agent-Orc
   * stored one there. */
  permission_mode: string | null
  approvals: Approval[]
  /** Runs in a git worktree of its own (removable once ended). */
  worktree: boolean
  /** From the configured share of the context on: hand over to a fresh session. */
  handover: { recommended: boolean; cache_cold: boolean }
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

/** Several agents side by side, as the workspace page arranges them. */
export interface Workspace {
  /** Open agents, in column order. */
  tabs: string[]
  /** How many columns fill the screen. */
  visible: number
  /** Columns set wider or narrower by dragging their divider, as a share of the screen width. */
  widths: Record<string, number>
  active: string | null
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

export interface Conversation {
  id: string
  title: string
  modified: number
  size: number
  /** Written to in the last minutes: probably still open elsewhere, e.g. in VS Code. */
  recently_active: boolean
}

/** An earlier conversation whose messages contain the searched words. */
export interface ConversationHit {
  id: string
  title: string
  modified: number
  /** Where the words were found first, with some context. */
  excerpt: string
  matches: number
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
    /** Start in a new git worktree on this new branch. */
    worktree: string | null = null,
  ) =>
    request<AgentSession>('POST', 'sessions', {
      body: { profile, path, resume, ...reasoning, conversation, worktree },
    }),
  /** Removes the worktree of an ended agent and its card; the branch only if merged. */
  removeWorktree: (sessionId: string) =>
    request<{ branch: string; branch_deleted: boolean }>(
      'POST',
      `sessions/${encodeURIComponent(sessionId)}/remove-worktree`,
    ),
  conversations: (profile: string, path: string) =>
    request<Conversation[]>('GET', 'conversations', { query: { profile, path } }),
  searchConversations: (profile: string, path: string, query: string) =>
    request<ConversationHit[]>('GET', 'conversations/search', { query: { profile, path, query } }),
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
  /** Answers a permission request in the agent's place of the terminal prompt. */
  answerApproval: (sessionId: string, requestId: string, allow: boolean) =>
    request<void>('POST', `sessions/${encodeURIComponent(sessionId)}/approval`, {
      body: { request: requestId, allow },
    }),
  changes: (sessionId: string) =>
    request<FileChange[]>('GET', `sessions/${encodeURIComponent(sessionId)}/changes`),
  changeDiff: (sessionId: string, path: string) =>
    request<FileDiff>('GET', `sessions/${encodeURIComponent(sessionId)}/changes/diff`, { query: { path } }),
  promptTemplates: () => request<PromptTemplate[]>('GET', 'prompt-templates'),
  storePromptTemplates: (templates: PromptTemplate[]) =>
    request<void>('PUT', 'prompt-templates', { body: templates }),
  consumption: () => request<ConsumptionRow[]>('GET', 'consumption'),
  /** Resumes the agent in its own session; a running answer and background tasks end. */
  restartSession: (sessionId: string) =>
    request<AgentSession>('POST', `sessions/${encodeURIComponent(sessionId)}/restart`),
  /** Types the handover request into the agent. */
  requestHandover: (sessionId: string) =>
    request<void>('POST', `sessions/${encodeURIComponent(sessionId)}/handover`),
  handoverAuto: () => request<{ auto: boolean }>('GET', 'handover/auto'),
  setHandoverAuto: (auto: boolean) => request<void>('PUT', 'handover/auto', { body: { auto } }),
  /** Takes effect at the agent's next start. */
  changePermissionMode: (sessionId: string, mode: string) =>
    request<void>('PUT', `sessions/${encodeURIComponent(sessionId)}/permission-mode`, { body: { mode } }),
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

  /** The server's public key a device subscribes to push messages with. */
  pushKey: () => request<{ key: string }>('GET', 'push/key'),
  subscribePush: (subscription: PushSubscriptionJSON) =>
    request<void>('POST', 'push/subscriptions', { body: subscription }),
  unsubscribePush: (endpoint: string) =>
    request<void>('DELETE', 'push/subscriptions', { query: { endpoint } }),
  /** A sample message to every subscribed device; returns how many took it. */
  testPush: () => request<{ delivered: number }>('POST', 'push/test'),

  /** Named workspaces by name; an unnamed one stays in its browser tab. */
  workspaces: () => request<Record<string, Workspace>>('GET', 'workspaces'),
  storeWorkspace: (name: string, workspace: Workspace) =>
    request<void>('PUT', `workspaces/${encodeURIComponent(name)}`, { body: workspace }),
  deleteWorkspace: (name: string) => request<void>('DELETE', `workspaces/${encodeURIComponent(name)}`),

  /** Store a file in the agent's folder; returns its path there, as the agent reads it. */
  attach: (sessionId: string, file: File) =>
    request<{ path: string }>('POST', `sessions/${encodeURIComponent(sessionId)}/attachments`, {
      upload: file,
      query: { name: file.name },
    }),

  /** engines: what the Whisper service offers to choose from (empty while it does not answer). */
  dictationSettings: () =>
    request<{ language: string; whisper: boolean; engines: string[] }>('GET', 'dictation'),
  /** Transcribe recorded speech on the chosen device; never switches device by itself. */
  dictate: (audio: Blob, device: DictationDevice, engine: string) =>
    request<{ text: string }>('POST', 'dictation', {
      upload: audio,
      // No engine: the service's default.
      query: engine ? { device, engine } : { device },
    }),

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

/**
 * WebSocket URL of a session's terminal, relative to the page like all API calls; the size goes
 * along, so tmux draws for this terminal from the start.
 */
export function terminalUrl(sessionId: string, cols: number, rows: number): string {
  const url = new URL(`api/sessions/${encodeURIComponent(sessionId)}/terminal`, document.baseURI)
  url.search = new URLSearchParams({ cols: String(cols), rows: String(rows) }).toString()
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}
