import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, type Workspace, type WorkspaceSet } from '../api'
import { useToast } from './useToast'
import { useWorkspaceChanges } from './useWorkspaceChanges'
import {
  announceWorkspace,
  emptyWorkspace,
  homeOf,
  loadTabState,
  nameWindow,
  rememberLastWorkspace,
  saveTabState,
  startWorkspace,
  tabShowsWorkspace,
  unnamedListed,
  useOtherTabs,
} from './useWorkspaceTab'

/**
 * The workspace a page shows, as the server keeps it for every device: loaded by the name in the
 * address, stored when it changes, updated when another device changes it, renamed and deleted.
 * `paused` holds storing back (a divider being dragged is stored once it is let go); `afterLoad`
 * runs once a workspace has been loaded (the page brings the right column into view).
 */
export function useWorkspaceStore(options: { paused: () => boolean; afterLoad: () => Promise<void> }) {
  const route = useRoute()
  const router = useRouter()
  const toast = useToast()
  const { t } = useI18n()

  const tabState = loadTabState()
  const name = ref<string | null>(null)
  /** The name field; becomes the name when it is left. */
  const nameInput = ref('')
  const savedNames = ref<string[]>([])
  // What the server held last: where each agent lives.
  const everyWorkspace = ref<WorkspaceSet | null>(null)
  const workspace = ref<Workspace>(emptyWorkspace())
  // Nothing is stored before the workspace has been loaded, or an empty one would replace it.
  const ready = ref(false)
  // The first load is through: the page can show everything at once.
  const loaded = ref(false)
  // Opened order of the iframes, apart from the column order: only appended and removed (moving
  // an iframe in the page would reload it).
  const frameIds = ref<string[]>([])
  const otherTabs = useOtherTabs()

  // The tabs of all workspaces in a fixed order: the unnamed one (null) first, if there is one to
  // show, then the named ones alphabetically. Names given in other tabs since this one loaded join
  // in as they are announced.
  const workspaceOrder = computed<(string | null)[]>(() => {
    const named = [...new Set([...savedNames.value, ...otherTabs.value, ...(name.value === null ? [] : [name.value])])].sort()
    const unnamedAgents = everyWorkspace.value?.unnamed.tabs.length ?? 0
    return unnamedListed(named.length, unnamedAgents, name.value === null) ? [null, ...named] : named
  })

  /** The other workspace an agent lives in (picking it here moves it); null if it has none. */
  function livesElsewhere(id: string): string | null {
    const home = everyWorkspace.value ? homeOf(everyWorkspace.value, id) : undefined
    return home === undefined || home === name.value ? null : (home ?? t('workspace.unnamed'))
  }

  /** Open a column at the end, or right after the column `after`; an open one stays where it is. */
  function addTab(id: string, after: string | null): void {
    const { tabs } = workspace.value
    if (tabs.includes(id)) return
    const position = after === null ? -1 : tabs.indexOf(after)
    if (position === -1) tabs.push(id)
    else tabs.splice(position + 1, 0, id)
    frameIds.value.push(id)
  }

  function removeTab(id: string): void {
    const { tabs } = workspace.value
    const index = tabs.indexOf(id)
    tabs.splice(index, 1)
    frameIds.value.splice(frameIds.value.indexOf(id), 1)
    delete workspace.value.widths[id]
    if (workspace.value.active === id) workspace.value.active = tabs[Math.max(0, index - 1)] ?? null
  }

  // What the server holds of this workspace, as text: a change is stored only when it differs,
  // and what arrived from the server is not stored back.
  let stored = ''
  // Counts the changes sent; an answer fetched before the latest one is already out of date.
  let sent = 0

  /** The tab remembers which workspace it shows; the other tabs hear it too. */
  function remember(): void {
    if (name.value !== null) rememberLastWorkspace(name.value)
    tabState.name = name.value
    saveTabState(tabState)
    nameWindow(name.value)
    announceWorkspace(name.value)
  }

  /** Store the workspace on the server, where every device shows it. */
  function persist(): void {
    if (!ready.value || options.paused()) return
    remember()
    const current = JSON.stringify(workspace.value)
    if (current === stored) return
    stored = current
    sent++
    const store =
      name.value === null ? api.storeUnnamedWorkspace(workspace.value) : api.storeWorkspace(name.value, workspace.value)
    void store.catch(toast.error)
  }

  onBeforeUnmount(() => announceWorkspace(null))
  watch(workspace, persist, { deep: true })

  /** Which agents are open here, in which order, as the server has it now; widths stay local. */
  function adoptAgents(agents: string[]): void {
    const current = workspace.value
    if (current.tabs.join() === agents.join()) return
    for (const id of current.tabs.filter((tab) => !agents.includes(tab))) {
      frameIds.value.splice(frameIds.value.indexOf(id), 1)
      delete current.widths[id]
    }
    frameIds.value.push(...agents.filter((id) => !current.tabs.includes(id)))
    current.tabs = [...agents]
    if (current.active !== null && !agents.includes(current.active)) current.active = agents[0] ?? null
    stored = JSON.stringify(current)
  }

  /** Another device changed a workspace: show what the server has. */
  async function fetchChanges(): Promise<void> {
    if (!ready.value) return
    const before = sent
    const everything = await api.workspaces()
    // A change of ours since is newer than this answer; the server's message about it follows.
    if (before !== sent || !ready.value) return
    everyWorkspace.value = everything
    savedNames.value = Object.keys(everything.named)
    const there = name.value === null ? everything.unnamed : everything.named[name.value]
    adoptAgents((there ?? emptyWorkspace()).tabs)
  }

  useWorkspaceChanges(() => fetchChanges().catch(toast.error))

  /** The address names the workspace, so a reload or a bookmark opens the same one. */
  function showName(): void {
    void router.replace({ path: '/workspace', query: name.value === null ? { unnamed: '1' } : { name: name.value } })
  }

  async function load(): Promise<void> {
    const requested = route.query.name
    const everything = await api.workspaces()
    if (route.query.unnamed !== undefined) name.value = null
    else if (typeof requested === 'string' && requested !== '') name.value = requested
    else name.value = tabShowsWorkspace() ? tabState.name : startWorkspace(everything)
    nameInput.value = name.value ?? ''
    everyWorkspace.value = everything
    savedNames.value = Object.keys(everything.named)
    const there = name.value === null ? everything.unnamed : everything.named[name.value]
    workspace.value = there ?? emptyWorkspace()
    stored = JSON.stringify(workspace.value)
    frameIds.value = [...workspace.value.tabs]
    ready.value = true
    loaded.value = true
    remember()
    await options.afterLoad()
  }

  load().catch(toast.error)

  // Another address while the page stays open: a different name (or the unnamed one) loads that
  // workspace, none shows the current name again.
  watch(
    () => [route.query.name, route.query.unnamed] as const,
    ([requested, unnamed]) => {
      if (!ready.value) return
      const wanted = typeof requested === 'string' && requested !== '' ? requested : null
      if (unnamed === undefined && wanted === null) {
        showName()
        return
      }
      if ((unnamed !== undefined ? null : wanted) === name.value) return
      ready.value = false
      load().catch(toast.error)
    },
  )

  /** Deleting moves the agents to the unnamed workspace, which this tab then shows. */
  async function deleteWorkspace(): Promise<void> {
    const current = name.value
    if (current === null) return
    // Nothing is stored for the workspace any more, or the delete would be undone.
    ready.value = false
    try {
      await api.deleteWorkspace(current)
    } catch (error) {
      ready.value = true
      toast.error(error)
      return
    }
    // The route watcher ignores a change while nothing is ready; so load the unnamed one here.
    await router.replace({ path: '/workspace', query: { unnamed: '1' } })
    load().catch(toast.error)
  }

  /** Naming stores the workspace on the server; renaming moves it there. */
  async function rename(): Promise<void> {
    const wanted = nameInput.value.trim()
    const current = name.value
    if (wanted === '' || wanted === current) {
      nameInput.value = current ?? ''
      return
    }
    if (savedNames.value.includes(wanted)) {
      toast.info(t('workspace.nameTaken', { name: wanted }))
      nameInput.value = current ?? ''
      return
    }
    try {
      await api.storeWorkspace(wanted, workspace.value)
      if (current !== null) await api.deleteWorkspace(current)
    } catch (error) {
      toast.error(error)
      return
    }
    savedNames.value = [...savedNames.value.filter((saved) => saved !== current), wanted]
    name.value = wanted
    nameInput.value = wanted
    // Stored just now, together with the agents leaving their old workspace.
    stored = JSON.stringify(workspace.value)
    sent++
    persist()
    showName()
  }

  return {
    name,
    nameInput,
    workspace,
    ready,
    loaded,
    frameIds,
    otherTabs,
    workspaceOrder,
    livesElsewhere,
    addTab,
    removeTab,
    persist,
    showName,
    rename,
    deleteWorkspace,
  }
}
