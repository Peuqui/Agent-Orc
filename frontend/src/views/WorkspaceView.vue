<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, type Workspace, type WorkspaceSet } from '../api'
import {
  COLUMN_CLOSE_EVENT,
  COLUMN_FULLSCREEN_EVENT,
  COLUMN_SWIPE_EVENT,
  MESSAGE_FIELD_SELECTOR,
} from '../columns'
import AppIcon from '../components/AppIcon.vue'
import DropdownMenu from '../components/DropdownMenu.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import HelpButton from '../components/HelpButton.vue'
import NavMenu from '../components/NavMenu.vue'
import WorkspaceNameField from '../components/WorkspaceNameField.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import SettingsMenu from '../components/SettingsMenu.vue'
import { moveInList, useReorder } from '../composables/useReorder'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { useWorkspaceChanges } from '../composables/useWorkspaceChanges'
import {
  announceWorkspace,
  emptyWorkspace,
  homeOf,
  jumpToWorkspace,
  loadTabState,
  MIN_VISIBLE,
  nameWindow,
  rememberLastWorkspace,
  saveTabState,
  startWorkspace,
  tabShowsWorkspace,
  unnamedListed,
  useOtherTabs,
  workspaceRoute,
} from '../composables/useWorkspaceTab'
import { PHONE_WIDTH, TABS_WIDTH, TOUCH_FIRST } from '../device'

// Several agents side by side. Every open agent is one column: its tab is the head of that
// column, both in one grid, so tab order and column order can never differ. The user picks
// how many columns fill the screen; further ones follow to the right (horizontal scrolling).
// Each column is the terminal page in an iframe; the iframes never move in the DOM (that
// would reload them), only their grid column changes.
// Narrowest and widest column a divider can set, as a share of the screen width.
const MIN_WIDTH_SHARE = 0.1
const MAX_WIDTH_SHARE = 1

interface Resize {
  id: string
  pointerId: number
  startX: number
  startShare: number
}

const route = useRoute()
const router = useRouter()
const toast = useToast()
const { t } = useI18n()
const { sessions } = useSessions()

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

// Opened order of the iframes, apart from the column order: only appended and removed.
const frameIds = ref<string[]>([])
const frames = ref<HTMLIFrameElement[]>([])
const heads = ref<HTMLElement[]>([])
const resize = ref<Resize | null>(null)
const row = ref<HTMLElement>()
const picking = ref(false)
const choosingWorkspace = ref(false)
const otherTabs = useOtherTabs()
// The tabs of all workspaces in a fixed order: the unnamed one (null) first, if there is one to
// show, then the named ones alphabetically. Names given in other tabs since this one loaded join
// in as they are announced.
const workspaceOrder = computed<(string | null)[]>(() => {
  const named = [...new Set([...savedNames.value, ...otherTabs.value, ...(name.value === null ? [] : [name.value])])].sort()
  const unnamedAgents = everyWorkspace.value?.unnamed.tabs.length ?? 0
  return unnamedListed(named.length, unnamedAgents, name.value === null) ? [null, ...named] : named
})

const notOpen = computed(() =>
  sessions.value.filter((session) => session.running && !workspace.value.tabs.includes(session.id)),
)

/** The other workspace an agent lives in (picking it here moves it); null if it has none. */
function livesElsewhere(id: string): string | null {
  const home = everyWorkspace.value ? homeOf(everyWorkspace.value, id) : undefined
  return home === undefined || home === name.value ? null : (home ?? t('workspace.unnamed'))
}

// On a phone one column fills the screen and a sideways swipe brings the next; the columns
// and widths set on a computer stay as they are for it.
const phone = ref(PHONE_WIDTH.matches)
const followPhoneWidth = (event: MediaQueryListEvent): void => {
  phone.value = event.matches
}
PHONE_WIDTH.addEventListener('change', followPhoneWidth)
onBeforeUnmount(() => PHONE_WIDTH.removeEventListener('change', followPhoneWidth))
// The workspaces as tabs in the header: on computers and wherever one row has room for them.
const tabsInHeader = ref(!PHONE_WIDTH.matches || TABS_WIDTH.matches)
const followTabsWidth = (): void => {
  tabsInHeader.value = !PHONE_WIDTH.matches || TABS_WIDTH.matches
}
PHONE_WIDTH.addEventListener('change', followTabsWidth)
TABS_WIDTH.addEventListener('change', followTabsWidth)
onBeforeUnmount(() => {
  PHONE_WIDTH.removeEventListener('change', followTabsWidth)
  TABS_WIDTH.removeEventListener('change', followTabsWidth)
})

// Only terminal and input field: no header, tabs, terminal bar or extra keys (the columns hear
// it as an event); where the browser offers it, its own fullscreen too.
const fullscreen = ref(false)

function tellColumns(frame: HTMLIFrameElement | undefined): void {
  frame?.contentWindow?.dispatchEvent(
    new CustomEvent(COLUMN_FULLSCREEN_EVENT, { detail: fullscreen.value }),
  )
}

watch(fullscreen, async (on) => {
  frames.value.forEach(tellColumns)
  if (!document.fullscreenEnabled) return
  // Leaving the browser's fullscreen by its own means (Esc, back gesture) ends ours as well.
  if (on && !document.fullscreenElement) await document.documentElement.requestFullscreen()
  if (!on && document.fullscreenElement) await document.exitFullscreen()
})

const followBrowserFullscreen = (): void => {
  if (!document.fullscreenElement) fullscreen.value = false
}
document.addEventListener('fullscreenchange', followBrowserFullscreen)
onBeforeUnmount(() => document.removeEventListener('fullscreenchange', followBrowserFullscreen))

// Phones have no room for a tab above each column: the terminal bar names it (and closes it).
const showTabs = computed(() => !phone.value && !fullscreen.value)

function widthShare(id: string): number {
  if (phone.value) return 1
  return workspace.value.widths[id] ?? 1 / workspace.value.visible
}

const gridStyle = computed(() => ({
  gridTemplateColumns: workspace.value.tabs
    .map((id) => `calc(100cqw * ${widthShare(id)})`)
    .join(' '),
}))

function tabName(id: string): string {
  const session = sessions.value.find((candidate) => candidate.id === id)
  return session ? sessionName(session) : id
}

function frameUrl(id: string): string {
  return `./#/terminal/${encodeURIComponent(id)}?embedded`
}

function column(id: string): string {
  return String(workspace.value.tabs.indexOf(id) + 1)
}

function headOf(id: string): HTMLElement | undefined {
  return heads.value.find((head) => head.dataset.tabId === id)
}

function frameOf(id: string): HTMLIFrameElement | undefined {
  return frames.value.find((frame) => frame.dataset.tab === id)
}

/** The message field of a column's terminal page (see MESSAGE_FIELD_ATTRIBUTE). */
function messageFieldOf(id: string): HTMLElement | null | undefined {
  return frameOf(id)?.contentDocument?.querySelector<HTMLElement>(MESSAGE_FIELD_SELECTOR)
}

/** Make a tab the active one and scroll its column into view (its tab may be hidden). */
async function activate(id: string): Promise<void> {
  workspace.value.active = id
  await nextTick()
  frameOf(id)?.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' })
}

/** Open a column at the end, or right after the column `after` (e.g. a terminal next to its
 * agent); an open one only becomes the active column. */
function open(id: string, after: string | null = null): void {
  picking.value = false
  const { tabs } = workspace.value
  if (!tabs.includes(id)) {
    const position = after === null ? -1 : tabs.indexOf(after)
    if (position === -1) tabs.push(id)
    else tabs.splice(position + 1, 0, id)
    frameIds.value.push(id)
  }
  void activate(id)
}

function closeTab(id: string): void {
  const { tabs } = workspace.value
  const index = tabs.indexOf(id)
  tabs.splice(index, 1)
  frameIds.value.splice(frameIds.value.indexOf(id), 1)
  delete workspace.value.widths[id]
  if (workspace.value.active === id) workspace.value.active = tabs[Math.max(0, index - 1)] ?? null
}

/** Sets the width of all columns: N of them fill the screen; individual widths are dropped. */
function changeVisible(delta: number): void {
  workspace.value.visible = Math.max(MIN_VISIBLE, workspace.value.visible + delta)
  workspace.value.widths = {}
}

/** Back to equal columns: the ones dragged wider or narrower return to the default. */
function resetWidths(): void {
  workspace.value.widths = {}
}

// A column's right divider sets its width (mouse or finger); a double click resets it.
function onDividerPointerDown(event: PointerEvent, id: string): void {
  if (event.button !== 0) return
  resize.value = { id, pointerId: event.pointerId, startX: event.clientX, startShare: widthShare(id) }
  const divider = event.currentTarget as HTMLElement
  divider.setPointerCapture(event.pointerId)
}

function onDividerPointerMove(event: PointerEvent): void {
  const current = resize.value
  const screenWidth = row.value?.clientWidth
  if (current === null || event.pointerId !== current.pointerId || !screenWidth) return
  const share = current.startShare + (event.clientX - current.startX) / screenWidth
  workspace.value.widths[current.id] = Math.min(MAX_WIDTH_SHARE, Math.max(MIN_WIDTH_SHARE, share))
}

function resetWidth(id: string): void {
  delete workspace.value.widths[id]
}

// Sorting: a whole tab is dragged and takes the place of the tab it is dropped on; the columns
// follow, as they belong to the same grid. Only the horizontal position counts, so the pointer
// may stray off the tab row. Dropped on another workspace's tab in the header, the agent moves
// to that workspace (target "workspace:<name>", the unnamed one has an empty name).
const WORKSPACE_DROP = 'workspace:'
const reorder = useReorder({
  targetAt: (x, y) => {
    const workspaceTab = document.elementFromPoint(x, y)?.closest<HTMLElement>('[data-workspace-drop]')
    if (workspaceTab) return WORKSPACE_DROP + workspaceTab.dataset.workspaceDrop
    return (
      workspace.value.tabs.find((id) => {
        const box = headOf(id)?.getBoundingClientRect()
        return box !== undefined && x >= box.left && x < box.right
      }) ?? null
    )
  },
  onDrop: (id, target) => {
    if (target.startsWith(WORKSPACE_DROP)) {
      api.moveSession(id, target.slice(WORKSPACE_DROP.length)).catch(toast.error)
    } else {
      moveInList(workspace.value.tabs, id, target)
    }
  },
  ignore: '[data-no-drag]',
})
const drag = reorder.drag

/** Scrolls the row to the next (1) or previous (-1) column start, where the swipe was made. */
function scrollColumns(direction: 1 | -1): void {
  const box = row.value
  if (!box) return
  const edge = box.getBoundingClientRect().left
  // Where each column starts, relative to the left edge of the screen: negative is scrolled past.
  const starts = workspace.value.tabs.map((id) => (frameOf(id)?.getBoundingClientRect().left ?? 0) - edge)
  const target = direction === 1 ? starts.find((start) => start > 1) : starts.findLast((start) => start < -1)
  if (target !== undefined) box.scrollBy({ left: target, behavior: 'smooth' })
}

// The iframes share this page's origin, so their pointer events can be watched directly: a
// touch inside a column makes it the active one (a focus change alone could be the terminal's
// own autofocus).
function onFrameLoad(id: string): void {
  const frameWindow = frameOf(id)?.contentWindow
  frameWindow?.addEventListener(
    'pointerdown',
    () => {
      workspace.value.active = id
    },
    true,
  )
  // Typing mostly happens inside a column: its shortcuts are caught there, before the terminal.
  frameWindow?.addEventListener('keydown', onShortcut, true)
  // A sideways swipe in any terminal moves the columns: phones bring the neighbouring column,
  // wider screens scroll the row to the next column start.
  frameWindow?.addEventListener(COLUMN_SWIPE_EVENT, (event) => {
    const direction = (event as CustomEvent<1 | -1>).detail
    if (!phone.value) return scrollColumns(direction)
    const neighbour = workspace.value.tabs[workspace.value.tabs.indexOf(id) + direction]
    if (neighbour !== undefined) void activate(neighbour)
  })
  frameWindow?.addEventListener(COLUMN_CLOSE_EVENT, () => closeTab(id))
  // A column loaded later (or reloaded) learns the current state.
  tellColumns(frameOf(id))
}

// Desktop shortcuts: Alt+Shift+1…9 goes to that column, Alt+Shift+←/→ to the previous or next
// workspace. Ctrl+digits cannot be used: the browser keeps them for its own tabs.
const COLUMN_KEYS = ['Digit1', 'Digit2', 'Digit3', 'Digit4', 'Digit5', 'Digit6', 'Digit7', 'Digit8', 'Digit9']
const WORKSPACE_STEPS: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1 }

function onShortcut(event: KeyboardEvent): void {
  if (!event.altKey || !event.shiftKey || event.ctrlKey || event.metaKey) return
  // The key's place, not its character: Shift turns "1" into "!" (layouts differ).
  const column = COLUMN_KEYS.indexOf(event.code)
  const step = WORKSPACE_STEPS[event.code]
  if (column >= 0) {
    const id = workspace.value.tabs[column]
    if (id === undefined) return
    event.preventDefault()
    void activate(id).then(() => messageFieldOf(id)?.focus())
  } else if (step !== undefined) {
    const order = workspaceOrder.value
    if (order.length < 2) return
    event.preventDefault()
    // As the bar shows them, going round at the ends.
    const here = order.indexOf(name.value)
    jumpToWorkspace(router, order[(here + step + order.length) % order.length])
  }
}

window.addEventListener('keydown', onShortcut, true)
onBeforeUnmount(() => window.removeEventListener('keydown', onShortcut, true))

// Turning the device changes how many columns fit; the active one (the red one) stays in view,
// not the one that happened to be there before. Done at once, as the layout has changed.
watch(phone, async () => {
  const id = workspace.value.active
  if (id === null) return
  await nextTick()
  frameOf(id)?.scrollIntoView({ behavior: 'instant', inline: phone.value ? 'start' : 'nearest', block: 'nearest' })
})

// Typing goes to the active column's input field; not on touch screens, where the focus would
// open the on-screen keyboard (a tap into the field does).
watch(
  () => workspace.value.active,
  async (id) => {
    if (id === null || TOUCH_FIRST.matches) return
    await nextTick()
    messageFieldOf(id)?.focus()
  },
)

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

/** Store the workspace on the server, where every device shows it; a divider once it is let go. */
function persist(): void {
  if (!ready.value || resize.value !== null) return
  remember()
  const current = JSON.stringify(workspace.value)
  if (current === stored) return
  stored = current
  sent++
  const store =
    name.value === null
      ? api.storeUnnamedWorkspace(workspace.value)
      : api.storeWorkspace(name.value, workspace.value)
  void store.catch(toast.error)
}

onBeforeUnmount(() => announceWorkspace(null))

watch(workspace, persist, { deep: true })
watch(resize, persist)

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

// Opened from the agent list, or a new agent started from the "+" menu.
function openRequested(): void {
  const id = route.query.open
  if (typeof id !== 'string') return
  const after = route.query.after
  open(id, typeof after === 'string' ? after : null)
  showName()
}

watch(() => route.query.open, () => ready.value && openRequested())

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
  if (typeof route.query.open === 'string') openRequested()
  else showName()
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

const deleting = ref(false)

/** Deleting moves the agents to the unnamed workspace, which this tab then shows. */
async function deleteThis(): Promise<void> {
  const current = name.value
  deleting.value = false
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
</script>

<template>
  <!-- Shown once the workspaces have arrived, so nothing flashes up that is replaced a moment later. -->
  <div class="flex h-dvh flex-col bg-slate-900">
    <template v-if="loaded">
      <ConfirmDialog
        v-if="deleting"
        :title="$t('workspace.delete')"
        :message="$t('workspace.confirmDelete', { name: name ?? '' })"
        :confirm-label="$t('workspace.delete')"
        danger
        @confirm="deleteThis"
        @close="deleting = false"
      />
      <!-- Compact buttons below md, so name, workspaces and usage fit on a phone. -->
      <header
        v-if="!fullscreen"
        class="flex flex-wrap items-center gap-1 border-b border-slate-800 px-1 py-1 max-md:[&_.btn-icon]:size-8"
      >
        <NavMenu />
        <!-- Narrow windows (not phones, which keep one row): name and workspaces move to a second
             row (this break starts it). -->
        <div v-if="!phone" class="order-last h-0 basis-full md:hidden" />
        <!-- Phones: the name, and the others in a list behind it, so everything fits in one row. -->
        <template v-if="!tabsInHeader">
          <WorkspaceNameField
            v-model="nameInput"
            class="flex-1"
            input-class="rounded-md px-2 py-1 font-semibold text-amber-300 placeholder:font-normal placeholder:text-slate-500 hover:bg-slate-800 focus:bg-slate-800"
            :placeholder="$t('workspace.unnamed')"
            :hint="$t('workspace.nameHint')"
            :deletable="name !== null"
            @rename="rename"
            @delete="deleting = true"
          />
          <DropdownMenu v-model:open="choosingWorkspace" panel-class="flex w-56 flex-col p-1">
            <template #trigger="{ toggle }">
              <button class="btn-icon" :aria-label="$t('workspace.others')" :title="$t('workspace.others')" @click="toggle">
                <AppIcon name="chevron" />
              </button>
            </template>
            <template v-for="other in workspaceOrder" :key="other ?? ''">
              <button
                v-if="other !== name"
                class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-700"
                @click="((choosingWorkspace = false), jumpToWorkspace(router, other))"
              >
                <AppIcon name="workspace" />{{ other ?? $t('workspace.unnamed') }}
              </button>
            </template>
            <button
              v-if="!workspaceOrder.includes(null)"
              class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-400 hover:bg-slate-700"
              @click="((choosingWorkspace = false), jumpToWorkspace(router, null))"
            >
              <AppIcon name="plus" />{{ $t('workspace.new') }}
            </button>
          </DropdownMenu>
        </template>
        <!-- Computers and upright tablets: all workspaces as tabs in a fixed order, the one shown
             is the name field. One click on another goes to the tab that shows it, otherwise
             here; a middle click opens a new tab. Narrow windows: in a second row, swipeable. -->
        <template v-else>
          <div v-if="!phone" class="order-last h-0 basis-full md:hidden" />
          <div
            class="flex min-w-0 items-center gap-1"
            :class="phone ? 'flex-1' : 'max-md:order-last max-md:flex-1 md:shrink-0'"
          >
            <!-- A new workspace starts unnamed; this is not the "+" that adds an agent (right); it stays in view while the tabs scroll. -->
            <button
              v-if="!workspaceOrder.includes(null)"
              class="ml-2 flex shrink-0 items-center gap-1 rounded-md border border-dashed border-slate-600 px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              :title="$t('workspace.new')"
              :aria-label="$t('workspace.new')"
              @click="jumpToWorkspace(router, null)"
            >
              <AppIcon name="plus" class="size-3.5" /><AppIcon name="workspace" class="size-4" />
            </button>
            <nav class="flex min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none]">
              <template v-for="tab in workspaceOrder" :key="tab ?? ''">
                <WorkspaceNameField
                  v-if="tab === name"
                  v-model="nameInput"
                  class="shrink-0"
                  input-class="rounded-md border border-amber-400/70 px-2 py-1 text-sm text-slate-100 placeholder:text-slate-300 field-sizing-content"
                  :placeholder="$t('workspace.unnamed')"
                  :hint="$t('workspace.nameHint')"
                  :deletable="name !== null"
                  @rename="rename"
                  @delete="deleting = true"
                />
                <a
                  v-else
                  :href="router.resolve(workspaceRoute(tab)).href"
                  class="flex shrink-0 items-center gap-1 rounded-md border border-slate-700 px-2 py-1 text-sm text-slate-300 hover:bg-slate-800 hover:text-slate-100"
                  :data-workspace-drop="tab ?? ''"
                  :class="drag?.active && drag.target === WORKSPACE_DROP + (tab ?? '') ? 'ring-2 ring-amber-400' : ''"
                  :title="tab !== null && otherTabs.has(tab) ? $t('workspace.openElsewhere') : $t('workspace.switchHere')"
                  @click.prevent="jumpToWorkspace(router, tab)"
                >
                  {{ tab ?? $t('workspace.unnamed') }}
                  <AppIcon v-if="tab !== null && otherTabs.has(tab)" name="external" class="size-3.5 text-slate-500" />
                </a>
              </template>
            </nav>
          </div>
        </template>
        <!-- Claude's usage, centred in the room between the workspaces and the buttons; it shrinks
             with the window. Not on phones: the name gets the room (the overview shows it). -->
        <QuotaPanel v-if="!phone" compact class="min-w-0 flex-1 overflow-hidden sm:px-3" />
        <DropdownMenu v-model:open="picking" right panel-class="flex w-64 flex-col gap-1 p-2">
          <template #trigger="{ toggle }">
            <button
              class="flex size-8 items-center justify-center rounded-md border border-slate-600 text-slate-300 hover:bg-slate-700"
              :aria-label="$t('workspace.add')"
              :title="$t('workspace.add')"
              @click="toggle"
            >
              <AppIcon name="plus" class="size-4" />
            </button>
          </template>
          <button
            v-for="session in notOpen"
            :key="session.id"
            class="rounded-md px-3 py-2 text-left hover:bg-slate-700"
            @click="open(session.id)"
          >
            {{ sessionName(session) }}
            <span v-if="livesElsewhere(session.id)" class="text-xs text-slate-500">
              · {{ $t('workspace.movesFrom', { name: livesElsewhere(session.id) }) }}
            </span>
          </button>
          <p v-if="notOpen.length === 0" class="px-3 py-2 text-sm text-slate-500">{{ $t('workspace.allOpen') }}</p>
          <RouterLink :to="{ path: '/files', query: { workspace: '1' } }" class="btn-primary mt-1">
            <AppIcon name="plus" />{{ $t('sessions.startNew') }}
          </RouterLink>
        </DropdownMenu>
        <!-- Columns as one boxed group: fewer | count | more. -->
        <div
          v-if="!phone"
          class="flex h-8 shrink-0 items-stretch divide-x divide-slate-600 overflow-hidden rounded-md border border-slate-600 text-sm text-slate-300"
          :title="$t('workspace.columns')"
        >
          <button class="w-7 hover:bg-slate-700" :aria-label="$t('workspace.fewerColumns')" @click="changeVisible(-1)">−</button>
          <span class="flex w-7 items-center justify-center text-slate-400">{{ workspace.visible }}</span>
          <button class="w-7 hover:bg-slate-700" :aria-label="$t('workspace.moreColumns')" @click="changeVisible(1)">+</button>
          <!-- Only while a column has been dragged to another width. -->
          <button
            v-if="Object.keys(workspace.widths).length"
            class="flex w-8 items-center justify-center hover:bg-slate-700"
            :title="$t('workspace.resetWidths')"
            :aria-label="$t('workspace.resetWidths')"
            @click="resetWidths"
          >
            <AppIcon name="widths" class="size-4" />
          </button>
        </div>
        <button class="btn-icon" :aria-label="$t('workspace.fullscreen')" :title="$t('workspace.fullscreen')" @click="fullscreen = true">
          <AppIcon name="expand" />
        </button>
        <!-- The device's settings, the same menu as in every other page's header. -->
        <SettingsMenu />
        <HelpButton />
      </header>
      <!-- The way back from fullscreen, small in the corner above the columns. -->
      <button
        v-if="fullscreen"
        class="fixed top-1 right-1 z-40 flex size-8 items-center justify-center rounded-md border border-slate-600 bg-slate-900/80 text-slate-300"
        :aria-label="$t('workspace.leaveFullscreen')"
        :title="$t('workspace.leaveFullscreen')"
        @click="fullscreen = false"
      >
        <AppIcon name="shrink" class="size-4" />
      </button>

      <p v-if="ready && workspace.tabs.length === 0" class="p-6 text-center text-slate-400">{{ $t('workspace.empty') }}</p>

      <!-- One scrolling row; 100cqw is its width, so N columns fill it exactly. -->
      <div
        ref="row"
        class="min-h-0 flex-1 overflow-x-auto"
        :class="{ 'snap-x snap-mandatory': resize === null, '[scrollbar-width:none]': phone }"
        style="container-type: inline-size"
      >
        <div class="grid h-full grid-rows-[auto_minmax(0,1fr)]" :style="gridStyle">
          <div
            v-for="id in showTabs ? workspace.tabs : []"
            :key="`head-${id}`"
            ref="heads"
            :data-tab-id="id"
            class="flex cursor-grab touch-pan-x snap-start items-center gap-1 border-b-2 bg-slate-900 py-1 pl-2 text-sm select-none [-webkit-touch-callout:none]"
            :class="[
              workspace.active === id ? 'border-red-500 text-slate-100' : 'border-slate-800 text-slate-400',
              drag?.active && drag.target === id && drag.id !== id ? 'ring-2 ring-amber-400 ring-inset' : '',
              drag?.active && drag.id === id ? 'opacity-50' : '',
            ]"
            :style="{ gridColumn: column(id), gridRow: '1' }"
            :title="$t('workspace.move')"
            @pointerdown="reorder.onPointerDown($event, id)"
            @pointermove="reorder.onPointerMove"
            @pointerup="reorder.onPointerUp"
            @pointercancel="reorder.cancel"
            @touchmove="reorder.onTouchMove"
            @contextmenu.prevent
          >
            <!-- The grabbing hand here too: the whole head is the handle for sorting. -->
            <button class="min-w-0 flex-1 cursor-grab truncate text-left font-medium" @click="activate(id)">
              {{ tabName(id) }}
            </button>
            <button
              class="px-2 text-slate-500 hover:text-slate-200"
              :aria-label="$t('workspace.close')"
              data-no-drag
              @click="closeTab(id)"
            >
              ×
            </button>
          </div>
          <iframe
            v-for="id in frameIds"
            :key="id"
            ref="frames"
            :data-tab="id"
            :data-active="workspace.active === id"
            :src="frameUrl(id)"
            :title="tabName(id)"
            class="h-full w-full snap-start bg-slate-900"
            :style="{ gridColumn: column(id), gridRow: '2' }"
            allow="microphone; clipboard-write"
            @load="onFrameLoad(id)"
          />
          <!-- Divider on each column's right edge, above the iframes (which would swallow it); on
               phones every column fills the screen, so there is nothing to divide. -->
          <div
            v-for="id in showTabs ? workspace.tabs : []"
            :key="`divider-${id}`"
            class="z-10 w-2 cursor-col-resize touch-none justify-self-end border-r border-slate-700 hover:bg-red-500/30"
            :class="{ 'bg-red-500/40': resize?.id === id }"
            :style="{ gridColumn: column(id), gridRow: '1 / span 2' }"
            :title="$t('workspace.resize')"
            @pointerdown="onDividerPointerDown($event, id)"
            @pointermove="onDividerPointerMove"
            @pointerup="resize = null"
            @pointercancel="resize = null"
            @dblclick="resetWidth(id)"
          />
        </div>
      </div>
    </template>
  </div>
</template>
