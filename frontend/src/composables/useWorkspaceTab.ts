import { computed, reactive } from 'vue'
import type { Router } from 'vue-router'
import type { Workspace, WorkspaceSet } from '../api'

// Another machine's app runs at an address of this machine's (below /hosts/<name>/), so it shares
// the browser's storage, window names and channels with it: what is kept per workspace carries
// the machine's name, or a workspace of one would be taken for one of the other of the same name.
// (This machine's own keep their names.)
let machine = ''

/** Says which machine's app this page is (null: this machine's own); before anything below is used. */
export function setMachine(host: string | null): void {
  machine = host === null ? '' : `@${host}`
}

// The workspace this browser tab shows, so each tab can show another one; a reload keeps it.
// All workspaces live on the server (every device shows the same); the tab only remembers which.
const tabStateKey = () => `agent-orc-workspace-tab${machine}`
// A named workspace's browser tab carries this window name, so opening it again brings that
// tab to the front instead of a second one.
const windowNamePrefix = () => `agent-orc-workspace${machine}:`
export const MIN_VISIBLE = 1
// A column's tab dropped on another workspace's tab moves the agent there: the drop target is this
// prefix and the workspace's name (empty for the unnamed one).
export const WORKSPACE_DROP = 'workspace:'
// The tabs of this browser tell each other which named workspace they show.
const channelName = () => `agent-orc-workspaces${machine}`

export interface TabState {
  /** Name of the workspace this tab shows; null for the unnamed one. */
  name: string | null
}

/** The unnamed workspace is listed while it is shown, holds agents, or is the only one there is. */
export function unnamedListed(namedCount: number, unnamedAgents: number, shown: boolean): boolean {
  return shown || namedCount === 0 || unnamedAgents > 0
}

/** The workspace an agent lives in: its name, null for the unnamed one, undefined for none. */
export function homeOf(workspaces: WorkspaceSet, agent: string): string | null | undefined {
  if (workspaces.unnamed.tabs.includes(agent)) return null
  return Object.entries(workspaces.named).find(([, workspace]) => workspace.tabs.includes(agent))?.[0]
}

export function emptyWorkspace(): Workspace {
  return { tabs: [], visible: MIN_VISIBLE, widths: {}, active: null }
}

export function loadTabState(): TabState {
  const stored = sessionStorage.getItem(tabStateKey())
  return { name: stored ? (JSON.parse(stored) as TabState).name : null }
}

/** This tab has shown a workspace before. */
export function tabShowsWorkspace(): boolean {
  return sessionStorage.getItem(tabStateKey()) !== null
}

// The workspace shown last on this device; a tab that has shown none yet starts with it.
const lastWorkspaceKey = () => `agent-orc-last-workspace${machine}`

export function rememberLastWorkspace(name: string): void {
  localStorage.setItem(lastWorkspaceKey(), name)
}

/**
 * The workspace a tab starts with that has shown none yet: the unnamed one while it holds agents
 * or nothing else exists, otherwise the one shown last on this device (or the first by name).
 */
export function startWorkspace(everything: WorkspaceSet): string | null {
  const named = Object.keys(everything.named).sort()
  if (named.length === 0 || everything.unnamed.tabs.length > 0) return null
  const last = localStorage.getItem(lastWorkspaceKey())
  return last !== null && named.includes(last) ? last : named[0]
}

export function saveTabState(state: TabState): void {
  sessionStorage.setItem(tabStateKey(), JSON.stringify(state))
}

/** Marks this browser tab as the one of the named workspace (none: an unnamed one). */
export function nameWindow(name: string | null): void {
  window.name = name === null ? '' : windowNamePrefix() + name
}

// The installed app (phones) has no browser tabs: workspaces take turns in its one window.
const installedApp = window.matchMedia('(display-mode: standalone)').matches

/** Workspaces get their own browser tabs, unless the installed app has none. */
export const ownTabs = !installedApp

/** Address of a named workspace or the unnamed one (null), with an agent to open in it. */
export function workspaceRoute(name: string | null, agent?: string) {
  const query: Record<string, string> = name === null ? { unnamed: '1' } : { name }
  if (agent !== undefined) query.open = agent
  return { path: '/workspace', query }
}

/** An agent opens in the workspace it lives in; one without any opens in this tab's. */
export function agentRoute(workspaces: WorkspaceSet | null, agent: string) {
  const home = workspaces ? homeOf(workspaces, agent) : undefined
  return home === undefined ? { path: '/workspace', query: { open: agent } } : workspaceRoute(home, agent)
}

/** Show the workspace in this window. */
function switchWorkspace(router: Router, name: string | null, agent?: string): void {
  void router.push(workspaceRoute(name, agent))
}

/**
 * Open the workspace in its own browser tab, or bring that tab to the front if it is open.
 * Browsers find a tab by its window name only among tabs opened from one another, so every
 * tab opens with this one as its opener (no "noopener").
 */
function openWorkspaceTab(router: Router, name: string | null, agent?: string): void {
  const address = router.resolve(workspaceRoute(name, agent)).href
  window.open(address, name === null ? '_blank' : windowNamePrefix() + name)
}

type TabMessage = { kind: 'ask' } | { kind: 'shown'; tab: string; name: string | null }

// Only pages that show workspaces join the channel, not the terminals inside their iframes.
let channel: BroadcastChannel | null = null
const thisTab = crypto.randomUUID()
/** Named workspace shown by each other tab of this browser, by tab. */
const shownByOtherTabs = reactive(new Map<string, string>())
let shownHere: string | null = null

function announce(): void {
  channel?.postMessage({ kind: 'shown', tab: thisTab, name: shownHere } satisfies TabMessage)
}

function joinChannel(): BroadcastChannel {
  if (channel !== null) return channel
  channel = new BroadcastChannel(channelName())
  channel.onmessage = (event: MessageEvent<TabMessage>) => {
    const message = event.data
    if (message.kind === 'ask') announce()
    else if (message.name === null) shownByOtherTabs.delete(message.tab)
    else shownByOtherTabs.set(message.tab, message.name)
  }
  // A closed tab no longer shows its workspace.
  window.addEventListener('pagehide', () => {
    shownHere = null
    announce()
  })
  channel.postMessage({ kind: 'ask' } satisfies TabMessage)
  return channel
}

/** Named workspaces open in other tabs of this browser. */
export function useOtherTabs() {
  joinChannel()
  return computed(() => new Set(shownByOtherTabs.values()))
}

/** Tells the other tabs which named workspace this one shows (null: none). */
export function announceWorkspace(name: string | null): void {
  joinChannel()
  shownHere = name
  announce()
}

/** A workspace already open in another tab is brought to the front, rather than opened twice. */
function openElsewhere(router: Router, name: string | null, agent?: string): boolean {
  if (!ownTabs || name === null || !new Set(shownByOtherTabs.values()).has(name)) return false
  openWorkspaceTab(router, name, agent)
  return true
}

/** From a workspace: jump to the other one, in its tab if it has one, otherwise here. */
export function jumpToWorkspace(router: Router, name: string | null): void {
  if (!openElsewhere(router, name)) switchWorkspace(router, name)
}

/**
 * From the overview: in its tab if it has one; in this window if it has shown no workspace yet
 * (or is the installed app); otherwise in a new browser tab of its own. The unnamed one always
 * opens here.
 */
export function openWorkspace(router: Router, name: string | null, agent?: string): void {
  if (name === null) return switchWorkspace(router, null, agent)
  if (openElsewhere(router, name, agent)) return
  if (!ownTabs || !tabShowsWorkspace() || loadTabState().name === name) switchWorkspace(router, name, agent)
  else openWorkspaceTab(router, name, agent)
}
