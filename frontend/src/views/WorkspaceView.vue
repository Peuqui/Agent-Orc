<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, type Workspace } from '../api'
import { COLUMN_CLOSE_EVENT, COLUMN_FULLSCREEN_EVENT, COLUMN_SWIPE_EVENT } from '../columns'
import AppIcon from '../components/AppIcon.vue'
import HelpButton from '../components/HelpButton.vue'
import NavMenu from '../components/NavMenu.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import { moveInList, useReorder } from '../composables/useReorder'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import {
  announceWorkspace,
  emptyWorkspace,
  jumpToWorkspace,
  loadTabState,
  MIN_VISIBLE,
  nameWindow,
  openWorkspace,
  saveTabState,
  useOtherTabs,
} from '../composables/useWorkspaceTab'
import { PHONE_WIDTH, TOUCH_FIRST } from '../device'

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
const workspace = ref<Workspace>(emptyWorkspace())
// Nothing is stored before the workspace has been loaded, or an empty one would replace it.
const ready = ref(false)

// Opened order of the iframes, apart from the column order: only appended and removed.
const frameIds = ref<string[]>([])
const frames = ref<HTMLIFrameElement[]>([])
const heads = ref<HTMLElement[]>([])
const resize = ref<Resize | null>(null)
const row = ref<HTMLElement>()
const picking = ref(false)
const choosingWorkspace = ref(false)
const otherTabs = useOtherTabs()
// Names given in other tabs since this one loaded join in as they are announced.
const otherNames = computed(() =>
  [...new Set([...savedNames.value, ...otherTabs.value])].filter((saved) => saved !== name.value).sort(),
)

const notOpen = computed(() =>
  sessions.value.filter((session) => session.running && !workspace.value.tabs.includes(session.id)),
)

// On a phone one column fills the screen and a sideways swipe brings the next; the columns
// and widths set on a computer stay as they are for it.
const phone = ref(PHONE_WIDTH.matches)
const followPhoneWidth = (event: MediaQueryListEvent): void => {
  phone.value = event.matches
}
PHONE_WIDTH.addEventListener('change', followPhoneWidth)
onBeforeUnmount(() => PHONE_WIDTH.removeEventListener('change', followPhoneWidth))

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
// may stray off the tab row.
const reorder = useReorder({
  targetAt: (x) =>
    workspace.value.tabs.find((id) => {
      const box = headOf(id)?.getBoundingClientRect()
      return box !== undefined && x >= box.left && x < box.right
    }) ?? null,
  onDrop: (id, target) => moveInList(workspace.value.tabs, id, target),
  ignore: '[data-no-drag]',
})
const drag = reorder.drag

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
  // A sideways swipe in its terminal brings the neighbouring column (phones).
  frameWindow?.addEventListener(COLUMN_SWIPE_EVENT, (event) => {
    const direction = (event as CustomEvent<1 | -1>).detail
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
    void activate(id).then(() => frameOf(id)?.contentDocument?.querySelector('textarea')?.focus())
  } else if (step !== undefined) {
    if (otherNames.value.length === 0) return
    event.preventDefault()
    // Alphabetical, as the bar shows them, going round at the ends; an unnamed workspace
    // stands before the first.
    const names = name.value === null ? otherNames.value : [...otherNames.value, name.value].sort()
    const here = name.value === null ? (step > 0 ? -1 : 0) : names.indexOf(name.value)
    jumpToWorkspace(router, names[(here + step + names.length) % names.length])
  }
}

window.addEventListener('keydown', onShortcut, true)
onBeforeUnmount(() => window.removeEventListener('keydown', onShortcut, true))

// Typing goes to the active column's input field; not on touch screens, where the focus would
// open the on-screen keyboard (a tap into the field does).
watch(
  () => workspace.value.active,
  async (id) => {
    if (id === null || TOUCH_FIRST.matches) return
    await nextTick()
    frameOf(id)?.contentDocument?.querySelector('textarea')?.focus()
  },
)

/** Store the workspace where it lives; a divider is stored once it is let go. */
function persist(): void {
  if (!ready.value || resize.value !== null) return
  if (name.value === null) tabState.unnamed = workspace.value
  else void api.storeWorkspace(name.value, workspace.value).catch(toast.error)
  tabState.name = name.value
  saveTabState(tabState)
  nameWindow(name.value)
  announceWorkspace(name.value)
}

onBeforeUnmount(() => announceWorkspace(null))

watch(workspace, persist, { deep: true })
watch(resize, persist)

/** The address names the workspace, so a reload or a bookmark opens the same one. */
function showName(): void {
  void router.replace({ path: '/workspace', query: name.value === null ? {} : { name: name.value } })
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
  if (route.query.new !== undefined) {
    name.value = null
    tabState.unnamed = emptyWorkspace()
  } else name.value = typeof requested === 'string' && requested !== '' ? requested : tabState.name
  nameInput.value = name.value ?? ''
  const named = await api.workspaces()
  savedNames.value = Object.keys(named)
  workspace.value = name.value === null ? tabState.unnamed : (named[name.value] ?? emptyWorkspace())
  frameIds.value = [...workspace.value.tabs]
  ready.value = true
  if (typeof route.query.open === 'string') openRequested()
  else showName()
}

load().catch(toast.error)

// Another address while the page stays open: a different name (or "new") loads that workspace,
// none shows the current name again.
watch(
  () => [route.query.name, route.query.new] as const,
  ([requested, fresh]) => {
    if (!ready.value) return
    if (fresh === undefined && requested === name.value) return
    if (fresh === undefined && (typeof requested !== 'string' || requested === '')) {
      showName()
      return
    }
    ready.value = false
    load().catch(toast.error)
  },
)

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
  if (current === null) tabState.unnamed = emptyWorkspace()
  persist()
  showName()
}
</script>

<template>
  <div class="flex h-dvh flex-col bg-slate-900">
    <!-- Compact buttons below md, so name, workspaces and usage fit on a phone. -->
    <header
      v-if="!fullscreen"
      class="flex flex-wrap items-center gap-1 border-b border-slate-800 px-1 py-1 max-md:[&_.btn-icon]:size-8"
    >
      <NavMenu />
      <!-- Narrow windows (not phones, which keep one row): name and workspaces move to a second
           row (this break starts it). -->
      <div v-if="!phone" class="order-last h-0 basis-full md:hidden" />
      <input
        v-model="nameInput"
        size="12"
        class="min-w-0 shrink rounded-md bg-transparent px-2 py-1 font-semibold placeholder:font-normal placeholder:text-slate-500 hover:bg-slate-800 focus:bg-slate-800 focus:outline-none"
        :class="phone ? 'flex-1' : 'w-28 max-md:order-last lg:w-44'"
        :placeholder="$t('workspace.unnamed')"
        :title="$t('workspace.nameHint')"
        :aria-label="$t('workspace.nameHint')"
        enterkeyhint="done"
        @keydown.enter="($event.target as HTMLInputElement).blur()"
        @change="rename"
      />
      <!-- The other workspaces, one click away: in their own tab if one shows them, otherwise
           here; a middle click opens a new tab. -->
      <!-- Phones: in a list behind the name, so everything fits in one row. -->
      <div v-if="phone" class="relative">
        <button class="btn-icon" :aria-label="$t('workspace.others')" :title="$t('workspace.others')" @click="choosingWorkspace = !choosingWorkspace">
          <AppIcon name="chevron" />
        </button>
        <div v-if="choosingWorkspace" class="fixed inset-0 z-30" @click="choosingWorkspace = false" />
        <div v-if="choosingWorkspace" class="card absolute top-full left-0 z-40 mt-1 flex w-56 flex-col p-1 shadow-xl">
          <button
            v-for="other in otherNames"
            :key="other"
            class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-700"
            @click="((choosingWorkspace = false), jumpToWorkspace(router, other))"
          >
            <AppIcon name="workspace" />{{ other }}
          </button>
          <button
            class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-400 hover:bg-slate-700"
            @click="((choosingWorkspace = false), openWorkspace(router, null))"
          >
            <AppIcon name="plus" />{{ $t('workspace.new') }}
          </button>
        </div>
      </div>
      <!-- Narrow windows: in the second row next to the name, swipeable. -->
      <nav
        v-else
        class="flex min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none] max-md:order-last max-md:flex-1 md:shrink-0"
      >
        <a
          v-for="other in otherNames"
          :key="other"
          :href="router.resolve({ path: '/workspace', query: { name: other } }).href"
          class="flex shrink-0 items-center gap-1 rounded-md border border-slate-700 px-2 py-0.5 text-sm text-slate-300 hover:bg-slate-800 hover:text-slate-100"
          :title="otherTabs.has(other) ? $t('workspace.openElsewhere') : $t('workspace.switchHere')"
          @click.prevent="jumpToWorkspace(router, other)"
        >
          {{ other }}<AppIcon v-if="otherTabs.has(other)" name="external" class="size-3.5 text-slate-500" />
        </a>
        <button
          class="flex shrink-0 items-center gap-1 rounded-md border border-dashed border-slate-700 px-2 py-0.5 text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-100"
          :title="$t('workspace.new')"
          :aria-label="$t('workspace.new')"
          @click="openWorkspace(router, null)"
        >
          <AppIcon name="plus" class="size-3.5" /><AppIcon name="workspace" class="size-4" />
        </button>
      </nav>
      <!-- Claude's usage, centred in the room between the workspaces and the buttons; it shrinks
           with the window. Not on phones: the name gets the room (the overview shows it). -->
      <QuotaPanel v-if="!phone" compact class="min-w-0 flex-1 overflow-hidden sm:px-3" />
      <div class="relative">
        <button
          class="flex size-8 items-center justify-center rounded-md border border-slate-600 text-slate-300 hover:bg-slate-700"
          :aria-label="$t('workspace.add')"
          :title="$t('workspace.add')"
          @click="picking = !picking"
        >
          <AppIcon name="plus" class="size-4" />
        </button>
        <div
          v-if="picking"
          class="card absolute top-full right-0 z-20 mt-1 flex w-64 flex-col gap-1 p-2 shadow-xl"
        >
          <button
            v-for="session in notOpen"
            :key="session.id"
            class="rounded-md px-3 py-2 text-left hover:bg-slate-700"
            @click="open(session.id)"
          >
            {{ sessionName(session) }}
          </button>
          <p v-if="notOpen.length === 0" class="px-3 py-2 text-sm text-slate-500">{{ $t('workspace.allOpen') }}</p>
          <RouterLink :to="{ path: '/files', query: { workspace: '1' } }" class="btn-primary mt-1">
            <AppIcon name="plus" />{{ $t('sessions.startNew') }}
          </RouterLink>
        </div>
      </div>
      <!-- Columns as one boxed group: fewer | count | more. -->
      <div
        v-if="!phone"
        class="flex h-8 shrink-0 items-stretch divide-x divide-slate-600 overflow-hidden rounded-md border border-slate-600 text-sm text-slate-300"
        :title="$t('workspace.columns')"
      >
        <button class="w-7 hover:bg-slate-700" :aria-label="$t('workspace.fewerColumns')" @click="changeVisible(-1)">−</button>
        <span class="flex w-7 items-center justify-center text-slate-400">{{ workspace.visible }}</span>
        <button class="w-7 hover:bg-slate-700" :aria-label="$t('workspace.moreColumns')" @click="changeVisible(1)">+</button>
      </div>
      <button class="btn-icon" :aria-label="$t('workspace.fullscreen')" :title="$t('workspace.fullscreen')" @click="fullscreen = true">
        <AppIcon name="expand" />
      </button>
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
  </div>
</template>
