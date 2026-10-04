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
export function switchWorkspace(router: Router, name: string | null): void {
  void router.push(workspaceRoute(name))
}

/** Open the workspace in its own browser tab, or bring that tab to the front if it is open. */
export function openWorkspaceTab(router: Router, name: string | null): void {
  const address = router.resolve(workspaceRoute(name)).href
  // A new unnamed tab must not start with a copy of this tab's state (noopener drops it).
  if (name === null) window.open(address, '_blank', 'noopener')
  else window.open(address, WINDOW_NAME_PREFIX + name)
}

/**
 * From the overview: in this window if it shows no agents yet (or is the installed app),
 * otherwise in the workspace's own browser tab.
 */
export function openWorkspace(router: Router, name: string | null): void {
  const state = loadTabState()
  const free = state.name === null && state.unnamed.tabs.length === 0
  if (!ownTabs || free || (name !== null && state.name === name)) switchWorkspace(router, name)
  else openWorkspaceTab(router, name)
}
