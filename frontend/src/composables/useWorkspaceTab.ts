import { computed, reactive } from 'vue'
import type { Router } from 'vue-router'
import type { Workspace } from '../api'

// The workspace of this browser tab, so each tab can show other agents; a reload keeps it. A
// named workspace lives on the server (every device and tab can open it by name), the tab then
// only remembers the name.
const TAB_STATE_KEY = 'agent-orc-workspace-tab'
// A named workspace's browser tab carries this window name, so opening it again brings that
// tab to the front instead of a second one.
const WINDOW_NAME_PREFIX = 'agent-orc-workspace:'
export const MIN_VISIBLE = 1
// The tabs of this browser tell each other which named workspace they show.
const CHANNEL_NAME = 'agent-orc-workspaces'

export interface TabState {
  /** Name of the workspace this tab shows; null for its own unnamed one. */
  name: string | null
  unnamed: Workspace
}

export function emptyWorkspace(): Workspace {
  return { tabs: [], visible: MIN_VISIBLE, widths: {}, active: null }
}

export function loadTabState(): TabState {
  const stored = sessionStorage.getItem(TAB_STATE_KEY)
  return stored ? (JSON.parse(stored) as TabState) : { name: null, unnamed: emptyWorkspace() }
}

export function saveTabState(state: TabState): void {
  sessionStorage.setItem(TAB_STATE_KEY, JSON.stringify(state))
}

/** Marks this browser tab as the one of the named workspace (none: an unnamed one). */
export function nameWindow(name: string | null): void {
  window.name = name === null ? '' : WINDOW_NAME_PREFIX + name
}

// The installed app (phones) has no browser tabs: workspaces take turns in its one window.
const installedApp = window.matchMedia('(display-mode: standalone)').matches

/** Workspaces get their own browser tabs, unless the installed app has none. */
export const ownTabs = !installedApp

/** Address of a named workspace, or of a new unnamed one (null). */
function workspaceRoute(name: string | null) {
  return { path: '/workspace', query: name === null ? { new: '1' } : { name } }
}

/** Show the workspace in this window. */
function switchWorkspace(router: Router, name: string | null): void {
  void router.push(workspaceRoute(name))
}

/**
 * Open the workspace in its own browser tab, or bring that tab to the front if it is open.
 * Browsers find a tab by its window name only among tabs opened from one another, so every
 * tab opens with this one as its opener (no "noopener"); a new unnamed one starts empty anyway
 * ("new" in its address), whatever state it inherits.
 */
function openWorkspaceTab(router: Router, name: string | null): void {
  const address = router.resolve(workspaceRoute(name)).href
  window.open(address, name === null ? '_blank' : WINDOW_NAME_PREFIX + name)
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
  channel = new BroadcastChannel(CHANNEL_NAME)
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
function openElsewhere(router: Router, name: string | null): boolean {
  if (!ownTabs || name === null || !new Set(shownByOtherTabs.values()).has(name)) return false
  openWorkspaceTab(router, name)
  return true
}

/** From a workspace: jump to the other one, in its tab if it has one, otherwise here. */
export function jumpToWorkspace(router: Router, name: string | null): void {
  if (!openElsewhere(router, name)) switchWorkspace(router, name)
}

/**
 * From the overview: in its tab if it has one; in this window if it shows no agents yet (or
 * is the installed app); otherwise in a new browser tab of its own.
 */
export function openWorkspace(router: Router, name: string | null): void {
  if (openElsewhere(router, name)) return
  const state = loadTabState()
  const free = state.name === null && state.unnamed.tabs.length === 0
  if (!ownTabs || free || (name !== null && state.name === name)) switchWorkspace(router, name)
  else openWorkspaceTab(router, name)
}
