import { ref } from 'vue'
import { hostOf, rootOf } from './hostPaths'

/** A model a profile offers at start; the note is shown beside it (e.g. until when it is free). */
export interface ModelChoice {
  name: string
  note: string | null
}

/** What the model dialog hands back: the agent (profile), its model if it has a choice, and the
 * level it runs with if it takes levels. */
export interface AgentChoice {
  profile: string
  model: string | null
  effort: string | null
}

export type ContextAction = 'clear' | 'compact'

export interface AgentProfile {
  name: string
  label: string
  /** Selectable reasoning effort; empty if the agent has none. */
  effort_levels: string[]
  /** The agent offers ultracode (workflow orchestration) next to the effort. */
  ultracode: boolean
  /** Switches its reasoning in place, without a restart (Claude: /effort). */
  effort_live: boolean
  /** Switches its model in place, without a restart (Claude: /model). */
  model_live: boolean
  /** What a running agent can do with its context in place (Claude: /clear, /compact). */
  context_actions: ContextAction[]
  /** Permission modes a session may start in; empty if the agent has none. */
  permission_modes: string[]
  /** A plain terminal, no agent: it may run next to a folder's agent. */
  terminal: boolean
  /** Where it keeps its conversations; agents with the same one go on with each other's. */
  conversations: string | null
  /** Offers a choice of models at start (GET agents/{name}/models). */
  models: boolean
  /** Shown in the start dialog when this profile is chosen; from the config. */
  hint: string | null
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

/** A message in AI-Connect, as its bridge stores it; timestamp in UTC (ISO). */
export interface PeerMessage {
  id: number
  from: string
  to: string
  content: string
  /** What came with it, e.g. an attached file. */
  context: string | null
  timestamp: string
}

/** A peer online in AI-Connect, with what it does right now. */
export interface Peer {
  name: string
  /** "busy", "idle", "waiting", ... */
  state: string | null
  state_detail: string | null
  /** The line it set on what it works on. */
  status: string | null
}

/** One line of AI-Connect's stream (GET peers/events, of this machine's own app). */
export type PeerEvent =
  | { event: 'peers'; peers: Peer[] }
  | ({ event: 'message' } & PeerMessage)
  | { event: 'history_end' }
  | { event: 'error'; kind: 'token_refused' | 'token_missing' | 'unreachable' | 'closed'; message?: string }

/** A note of a notebook; the text is Markdown. */
export interface Note {
  title: string
  text: string
}

export interface NoteFolder {
  name: string
  notes: Note[]
}

/** Notes, loose and in folders; one tab of the notes page. */
export interface Notebook {
  notes: Note[]
  folders: NoteFolder[]
}

/** One text the agent wrote while answering. */
export interface AnswerText {
  id: string
  /** ISO time (UTC). */
  time: string
  /** Markdown. */
  text: string
}

/** What the user typed while the agent was answering. */
export interface Interjection {
  id: string
  /** When it was typed (ISO, UTC). */
  time: string
  text: string
  /** Pictures that came with it (their content is not shown). */
  images: number
  /** The agent has not taken it yet. */
  pending: boolean
}

/** A request of the user and the texts the agent wrote in answer, the last one the summary. */
export interface Turn {
  id: string
  time: string
  prompt: string
  /** Pictures that came with the request. */
  images: number
  texts: AnswerText[]
  interjections: Interjection[]
}

/** The Whisper service's engine and, per device, its precision (Parakeet) or model (Whisper). */
export interface DictationService {
  engine: string
  gpu: string
  cpu: string
}

/** A request spoken to the agent on the Echo and sent on (its time is when it was sent). */
export interface SpokenRequest {
  id: string
  time: string
  request: string
  /** The sentence as the recognition heard it, with the agent's name. */
  heard: string
  /** How well the spoken name matched the agent's, 0 to 1; null when none was spoken. */
  score: number | null
  /** The recording is still kept (it goes with a stopped agent and after some days). */
  recording: boolean
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

/** A prompt typed into an agent later: planned by the user, or the resume after its usage limit. */
export interface ScheduledPrompt {
  id: string
  session: string
  text: string
  /** Unix seconds. */
  at: number
  reason: 'user' | 'limit'
}

export interface ExistingPath {
  path: string
  kind: 'file' | 'folder'
}

export type HandoverProgress = 'asked' | 'working' | 'done' | 'advised'

export interface AgentSession {
  id: string
  profile: string
  path: string
  running: boolean
  exit_status: number | null
  created: number
  /** A plain terminal, next to the folder's agent if it has one. */
  terminal: boolean
  /** The model chosen at start (profiles with a choice of models). */
  chosen_model: string | null
  /** Sets a further agent in the folder apart from the first; null for the first. */
  suffix: string | null
  /** The time of the newest answer looked at, on any device ("" none yet). */
  answers_seen: string
  /** The folder's name, with the suffix of a further agent. */
  name: string
  /** The levels its slider offers: the profile's, or those of the chosen model. */
  effort_levels: string[]
  /** Reported by the agent itself (Claude: via `agent-orc statusline`); null until it reports. */
  model: string | null
  effort: string | null
  /** The agent is working on an answer (reported by its hooks). */
  busy: boolean
  /** Stored for the folder; the agent reads it at start. */
  ultracode: boolean
  /** Permission mode the folder's sessions start in (the configured one until the folder has
   * its own); null for agents without permission modes. */
  permission_mode: string | null
  approvals: Approval[]
  /** Earliest first; typed once due and the agent is idle. */
  scheduled: ScheduledPrompt[]
  /** Runs in a git worktree of its own (removable once ended). */
  worktree: boolean
  /** From the configured share of the context on: hand over to a fresh session; due shortly
   * before the cache of the resting agent expires; where a handover stands (handover.py). */
  handover: { recommended: boolean; due: boolean; progress: HandoverProgress | null }
  /** When the prompt cache expires: the last request (Unix seconds) plus its window; the
   * handover is due lead_seconds before. Null until the agent has answered. */
  cache: { last_request: number; window_seconds: number; lead_seconds: number } | null
  /** A reasoning change waits until the current answer is finished. */
  effort_pending: boolean
  pending_effort: string | null
  pending_ultracode: boolean | null
  /** A model change of a busy agent waits until the current answer is finished. */
  pending_model: string | null
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

/** The unnamed workspace and the named ones by name. */
export interface WorkspaceSet {
  unnamed: Workspace
  named: Record<string, Workspace>
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
  /** A text key (macro): Enter follows the text, as when sending from the input field. */
  submit: boolean
}

export interface TerminalSettings {
  keys: TerminalKey[][]
  /** The user arranged the keys (for every device); otherwise the config's hold. */
  keys_arranged: boolean
}

/** A project's conversations for the clean-up list. */
export interface ProjectConversations {
  /** The name of Claude's transcript directory, to address deletions. */
  directory: string
  folder: string
  conversations: CleanupConversation[]
}

export interface HostsState {
  /** This machine's name. */
  self: string
  hosts: { name: string; online: boolean }[]
}

export interface CleanupConversation extends Conversation {
  /** An agent runs in it or it was written to just now: cannot be deleted. */
  in_use: boolean
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

/** The machine whose app this page is (served below /hosts/<name>/ by this machine's own), if it
 * is not this machine's own. */
export const currentHost = hostOf(new URL(document.baseURI).pathname)

/** The address of this machine's own app, from wherever the page is. */
export function rootAddress(): string {
  const root = new URL(document.baseURI)
  root.pathname = rootOf(root.pathname)
  root.search = ''
  root.hash = ''
  return root.href
}

async function request<T>(
  method: string,
  path: string,
  /** body is sent as JSON, upload (e.g. recorded audio) as it is. `host` asks another machine's
   * app, `fromRoot` this machine's own whichever machine's page this is. */
  options: {
    body?: unknown
    upload?: Blob
    query?: Record<string, string>
    host?: string
    fromRoot?: boolean
  } = {},
): Promise<T> {
  // Relative to the page, so the app also works under a reverse-proxy sub-path (and below
  // /hosts/<name>/, where it is another machine's).
  const base = options.fromRoot ? rootAddress() : document.baseURI
  const hostPrefix = options.host === undefined ? '' : `hosts/${encodeURIComponent(options.host)}/`
  const url = new URL(`${hostPrefix}api/${path}`, base)
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
  // Only an answer of the page's own app says whether the page is out of date: another machine's
  // app may be at another build, and from a page of its own the root's is not the page's.
  if ((options.host ?? (options.fromRoot ? null : currentHost)) === currentHost) checkBuild(response)
  if (response.status === 401 && path !== 'login' && path !== 'scope/unlock') {
    // Another machine's app has no login: it is this machine's that has run out, so to there.
    if (currentHost === null) authenticated.value = false
    else window.location.assign(rootAddress())
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
  /** Stores the extra keys for every device. */
  arrangeKeys: (rows: TerminalKey[][]) => request<void>('PUT', 'terminal/keys', { body: rows }),
  /** Back to the extra keys of the config. */
  resetKeys: () => request<void>('DELETE', 'terminal/keys'),
  sessions: () => request<AgentSession[]>('GET', 'sessions'),
  /** This machine's name and the others', from this machine's own app (also from another's page). */
  hosts: () => request<HostsState>('GET', 'hosts', { fromRoot: true }),
  /** The agents of another machine, as that machine's own app reports them. */
  hostSessions: (host: string) => request<AgentSession[]>('GET', 'sessions', { host, fromRoot: true }),
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
    /** For profiles with a choice of models (AgentProfile.models). */
    model: string | null = null,
    /** The workspace the agent joins (null: the one it is in; "": the unnamed one). */
    workspace: string | null = null,
    /** Sets a further agent in the folder apart from the first (required once that one runs). */
    suffix: string | null = null,
  ) =>
    request<AgentSession>('POST', 'sessions', {
      body: { profile, path, model, resume, ...reasoning, conversation, worktree, workspace, suffix },
    }),
  /** Moves an agent to a workspace ("": the unnamed one); the server keeps it, every device shows it. */
  moveSession: (sessionId: string, workspace: string) =>
    request<void>('PUT', `sessions/${encodeURIComponent(sessionId)}/workspace`, { body: { workspace } }),
  /** The models a profile offers at start (e.g. the local ones of llama-swap). */
  agentModels: (profile: string) => request<ModelChoice[]>('GET', `agents/${encodeURIComponent(profile)}/models`),
  /** The levels the profile takes with this model; empty: no level at all. */
  agentLevels: (profile: string, model: string) =>
    request<string[]>('GET', `agents/${encodeURIComponent(profile)}/levels`, { query: { model } }),
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
  /** The reasoning the agent of this profile, folder and suffix last had (to preselect). */
  storedReasoning: (profile: string, path: string, suffix: string | null) =>
    request<Reasoning>('GET', 'effort', { query: suffix === null ? { profile, path } : { profile, path, suffix } }),
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
  /** The consumption on this machine, or on another (`host`). A page of another machine's app asks
   * this machine's own, too: it sums them all. */
  consumption: (host?: string) => request<ConsumptionRow[]>('GET', 'consumption', { host, fromRoot: true }),
  /** Resumes the agent in its own session; a running answer and background tasks end. */
  restartSession: (sessionId: string, model: string | null = null, effort: string | null = null) =>
    request<AgentSession>('POST', `sessions/${encodeURIComponent(sessionId)}/restart`, { body: { model, effort } }),
  /** Switches the agent to the model: in place if it can, otherwise by resuming it; applied is
   * false while a busy agent finishes its answer first. */
  changeModel: (sessionId: string, model: string, effort: string | null) =>
    request<{ applied: boolean }>('POST', `sessions/${encodeURIComponent(sessionId)}/model`, {
      body: { model, effort },
    }),
  /** Starts another agent (profile) in the session's place; a running answer and background
   * tasks end. The conversation goes on if both keep it in the same place. */
  changeProfile: (sessionId: string, choice: AgentChoice) =>
    request<AgentSession>('POST', `sessions/${encodeURIComponent(sessionId)}/profile`, { body: choice }),
  /** Types the prompt into the agent at `at` (Unix seconds), once it is idle. */
  schedulePrompt: (sessionId: string, text: string, at: number) =>
    request<ScheduledPrompt>('POST', `sessions/${encodeURIComponent(sessionId)}/scheduled`, {
      body: { text, at },
    }),
  cancelScheduled: (promptId: string) =>
    request<void>('DELETE', `scheduled/${encodeURIComponent(promptId)}`),
  /** The agent's answers up to this time were looked at (the server only goes forward). */
  markAnswersSeen: (sessionId: string, time: string) =>
    request<void>('PUT', `sessions/${encodeURIComponent(sessionId)}/answers-seen`, { body: { time } }),
  /** Types the message into the agent and submits it (the server types, then presses Enter). */
  sendMessage: (sessionId: string, text: string) =>
    request<void>('POST', `sessions/${encodeURIComponent(sessionId)}/message`, { body: { text } }),
  /** Types the same prompt into each of the (running) agents; without submit it only lands in
   * their input and the user sends it there. */
  broadcast: (sessionIds: string[], text: string, submit = true) =>
    request<void>('POST', 'broadcast', { body: { sessions: sessionIds, text, submit } }),
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
  /** Empties or shrinks the context of an idle agent, without a restart. */
  changeContext: (sessionId: string, action: ContextAction) =>
    request<void>('POST', `sessions/${encodeURIComponent(sessionId)}/context/${action}`),
  cancelModelChange: (sessionId: string) =>
    request<void>('DELETE', `sessions/${encodeURIComponent(sessionId)}/model`),
  stopSession: (id: string) => request<void>('DELETE', `sessions/${encodeURIComponent(id)}`),
  /** The terminal as plain text, for selecting and copying. */
  /** Where a picture of a request or of something typed during an answer is served (index from 0). */
  answerImageUrl: (sessionId: string, entryId: string, index: number) =>
    `api/sessions/${encodeURIComponent(sessionId)}/images/${encodeURIComponent(entryId)}/${index}`,
  /** Whether answers can be read on the Echo, what the settings call it, the rooms connected now, the longest text. */
  // AI-Connect is one for all machines, and this machine's own app reads it along: its pages (and
  // those of another machine's app) ask this one.
  peers: () => request<{ configured: boolean; user_name: string }>('GET', 'peers', { fromRoot: true }),
  peerMessage: (to: string[], content: string) =>
    request<{ sent: { to: string; id: number; online: boolean }[] }>('POST', 'peers/message', { body: { to, content }, fromRoot: true }),

  announce: () =>
    request<{ configured: boolean; rooms: string[]; max_chars: number; label: string }>('GET', 'announce'),
  /** Has the text said on the Echo of the room ("*": all); returns once it is queued. */
  announceTexts: (room: string, texts: string[], speaker: string) =>
    request<void>('POST', 'announce', { body: { room, texts, speaker } }),
  /** Where a picture attached for the agent is served (the file name in its uploads folder). */
  uploadUrl: (sessionId: string, name: string) =>
    `api/sessions/${encodeURIComponent(sessionId)}/uploads/${encodeURIComponent(name)}`,
  /** The last requests of the user with the agent's texts, oldest first (no thoughts or tools). */
  answers: (sessionId: string, turns: number) =>
    request<Turn[]>('GET', `sessions/${encodeURIComponent(sessionId)}/answers`, { query: { turns: String(turns) } }),
  /** Where the recording of something said on the Echo is served (the id of its entry). */
  recordingUrl: (id: string) => `api/voice/${encodeURIComponent(id)}/audio`,
  /** What was spoken to the agent on the Echo, to mark those requests in its answers. */
  spoken: (sessionId: string) => request<SpokenRequest[]>('GET', `sessions/${encodeURIComponent(sessionId)}/voice`),
  sessionText: (id: string) =>
    request<{ text: string }>('GET', `sessions/${encodeURIComponent(id)}/text`),

  // The usage limits belong to the account, which this machine's own app reports (the machine
  // that serves the page); a page of another machine's app asks this one, too.
  quota: () => request<AgentQuota[]>('GET', 'quota', { fromRoot: true }),
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

  /** Every workspace, as the server keeps them for all devices. */
  workspaces: () => request<WorkspaceSet>('GET', 'workspaces'),
  /** An agent leaves its other workspaces: it lives in one. */
  storeUnnamedWorkspace: (workspace: Workspace) =>
    request<void>('PUT', 'unnamed-workspace', { body: workspace }),
  storeWorkspace: (name: string, workspace: Workspace) =>
    request<void>('PUT', `workspaces/${encodeURIComponent(name)}`, { body: workspace }),
  deleteWorkspace: (name: string) => request<void>('DELETE', `workspaces/${encodeURIComponent(name)}`),

  /** Every notebook by name, in tab order, as the server keeps them for all devices. */
  notebooks: () => request<Record<string, Notebook>>('GET', 'notebooks'),
  /** Stores the whole notebook; a new name adds a tab. */
  storeNotebook: (name: string, notebook: Notebook) =>
    request<void>('PUT', `notebooks/${encodeURIComponent(name)}`, { body: notebook }),
  renameNotebook: (name: string, newName: string) =>
    request<void>('PUT', `notebooks/${encodeURIComponent(name)}/name`, { body: { name: newName } }),
  deleteNotebook: (name: string) => request<void>('DELETE', `notebooks/${encodeURIComponent(name)}`),

  /** Stores a file for a note; returns the address the note links to it with. */
  attachToNote: (file: File) =>
    request<{ url: string }>('POST', 'notes/files', { upload: file, query: { name: file.name } }),
  /** Store a file in the agent's folder; returns its path there, as the agent reads it. */
  attach: (sessionId: string, file: File) =>
    request<{ path: string }>('POST', `sessions/${encodeURIComponent(sessionId)}/attachments`, {
      upload: file,
      query: { name: file.name },
    }),

  /** service: what the Whisper service transcribes with, null while it does not answer. */
  dictationSettings: () =>
    request<{ language: string; whisper: boolean; service: DictationService | null }>('GET', 'dictation'),
  /** Transcribe recorded speech on the chosen device; never switches device by itself. */
  dictate: (audio: Blob, device: DictationDevice) =>
    request<{ text: string }>('POST', 'dictation', { upload: audio, query: { device } }),

  listFiles: (path: string) => request<FileEntry[]>('GET', 'files', { query: { path } }),
  createFolder: (parent: string, name: string) =>
    request<{ path: string }>('POST', 'files/folder', { body: { parent, name } }),
  rename: (path: string, newName: string) =>
    request<{ path: string }>('POST', 'files/rename', { body: { path, new_name: newName } }),
  readFile: (path: string) => request<TextFile>('GET', 'files/content', { query: { path } }),
  /** Of the paths an agent wrote (relative to base, absolute or from ~), those that exist. */
  existingPaths: (base: string, candidates: string[]) =>
    request<Record<string, ExistingPath>>('POST', 'files/existing', { body: { base, candidates } }),
  writeFile: (path: string, content: string, expectedVersion: string | null) =>
    request<{ version: string }>('PUT', 'files/content', {
      body: { path, content, expected_version: expectedVersion },
    }),
  moveToTrash: (path: string) => request<TrashEntry>('POST', 'files/trash', { body: { path } }),

  listTrash: () => request<TrashEntry[]>('GET', 'trash'),
  restore: (id: string) => request<{ path: string }>('POST', 'trash/restore', { body: { id } }),
  deleteFromTrash: (id: string) => request<void>('DELETE', `trash/${encodeURIComponent(id)}`),
  emptyTrash: () => request<void>('DELETE', 'trash'),

  listAllConversations: () => request<ProjectConversations[]>('GET', 'conversations/all'),
  /** For good, not into the trash. */
  deleteConversations: (conversations: { directory: string; id: string }[]) =>
    request<{ deleted: number; freed_bytes: number }>('POST', 'conversations/delete', {
      body: { conversations },
    }),
}

/**
 * WebSocket URL of a session's terminal, relative to the page like all API calls; the size goes
 * along, so tmux draws for this terminal from the start.
 */
/** The file as it is, for pictures and downloads (the login cookie goes along). */
export function rawFileUrl(path: string, download = false): string {
  const url = new URL('api/files/raw', document.baseURI)
  url.search = new URLSearchParams(download ? { path, download: 'true' } : { path }).toString()
  return url.toString()
}

export function terminalUrl(sessionId: string, cols: number, rows: number): string {
  const url = new URL(`api/sessions/${encodeURIComponent(sessionId)}/terminal`, document.baseURI)
  url.search = new URLSearchParams({ cols: String(cols), rows: String(rows) }).toString()
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}
