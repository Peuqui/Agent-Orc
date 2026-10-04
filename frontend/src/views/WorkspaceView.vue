<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { useSessions } from '../composables/useSessions'
import { baseName } from '../format'

// Several agents side by side. Every open agent is one column: its tab is the head of that
// column, both in one grid, so tab order and column order can never differ. The user picks
// how many columns fill the screen; further ones follow to the right (horizontal scrolling).
// Each column is the terminal page in an iframe; the iframes never move in the DOM (that
// would reload them), only their grid column changes.
const STORAGE_KEY = 'agent-orc-columns'
const MIN_VISIBLE = 1
// A mouse drag starts after this much movement; less is a click.
const DRAG_THRESHOLD_PX = 8
// A finger first holds a tab this long, so that swiping across the tabs still scrolls.
const TOUCH_HOLD_MS = 400
// Narrowest and widest column a divider can set, as a share of the screen width.
const MIN_WIDTH_SHARE = 0.1
const MAX_WIDTH_SHARE = 1

interface Workspace {
  /** Open agents, in column order. */
  tabs: string[]
  /** How many columns fill the screen. */
  visible: number
  /** Columns set wider or narrower by dragging their divider, as a share of the screen width. */
  widths: Record<string, number>
  active: string | null
}

interface Resize {
  id: string
  pointerId: number
  startX: number
  startShare: number
}

interface Drag {
  id: string
  pointerId: number
  startX: number
  startY: number
  /** False until the pointer has moved (mouse) or was held (finger) long enough. */
  active: boolean
  /** The tab whose place it takes when dropped. */
  target: string | null
}

const route = useRoute()
const router = useRouter()
const { sessions } = useSessions()

function loadWorkspace(): Workspace {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored
    ? (JSON.parse(stored) as Workspace)
    : { tabs: [], visible: MIN_VISIBLE, widths: {}, active: null }
}

const workspace = ref<Workspace>(loadWorkspace())
watch(workspace, (value) => localStorage.setItem(STORAGE_KEY, JSON.stringify(value)), { deep: true })

// Opened order of the iframes, apart from the column order: only appended and removed.
const frameIds = ref<string[]>([...workspace.value.tabs])
const frames = ref<HTMLIFrameElement[]>([])
const heads = ref<HTMLElement[]>([])
const drag = ref<Drag | null>(null)
const resize = ref<Resize | null>(null)
const row = ref<HTMLElement>()
const picking = ref(false)

const notOpen = computed(() =>
  sessions.value.filter((session) => session.running && !workspace.value.tabs.includes(session.id)),
)

function widthShare(id: string): number {
  return workspace.value.widths[id] ?? 1 / workspace.value.visible
}

const gridStyle = computed(() => ({
  gridTemplateColumns: workspace.value.tabs
    .map((id) => `calc(100cqw * ${widthShare(id)})`)
    .join(' '),
}))

function tabName(id: string): string {
  const session = sessions.value.find((candidate) => candidate.id === id)
  return session ? baseName(session.path) : id
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

/** Make a tab the active one and scroll its column into view. */
async function activate(id: string): Promise<void> {
  workspace.value.active = id
  await nextTick()
  headOf(id)?.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' })
}

function open(id: string): void {
  picking.value = false
  if (!workspace.value.tabs.includes(id)) {
    workspace.value.tabs.push(id)
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

// Sorting: a whole tab is dragged and takes the place of the tab it is dropped on (the others
// move up); the columns follow, as they belong to the same grid.
let holdTimer: number | undefined

function startDrag(element: HTMLElement): void {
  if (drag.value === null) return
  drag.value.active = true
  // Keeps the pointer events coming while the pointer leaves the tab.
  element.setPointerCapture(drag.value.pointerId)
}

function onTabPointerDown(event: PointerEvent, id: string): void {
  if (event.button !== 0) return
  const element = event.currentTarget as HTMLElement
  const { pointerId, clientX, clientY } = event
  drag.value = { id, pointerId, startX: clientX, startY: clientY, active: false, target: null }
  if (event.pointerType === 'touch') holdTimer = window.setTimeout(() => startDrag(element), TOUCH_HOLD_MS)
}

function onTabPointerMove(event: PointerEvent): void {
  const current = drag.value
  if (current === null || event.pointerId !== current.pointerId) return
  if (!current.active) {
    const moved = Math.hypot(event.clientX - current.startX, event.clientY - current.startY)
    if (moved < DRAG_THRESHOLD_PX) return
    // A finger moving before the hold is up swipes the row instead.
    if (event.pointerType === 'touch') return endDrag()
    startDrag(event.currentTarget as HTMLElement)
  }
  current.target =
    workspace.value.tabs.find((id) => {
      const box = headOf(id)?.getBoundingClientRect()
      return box !== undefined && event.clientX >= box.left && event.clientX < box.right
    }) ?? null
}

function onTabPointerUp(event: PointerEvent): void {
  const current = drag.value
  if (current === null || event.pointerId !== current.pointerId) return
  endDrag()
  if (!current.active || current.target === null || current.target === current.id) return
  const { tabs } = workspace.value
  const to = tabs.indexOf(current.target)
  tabs.splice(tabs.indexOf(current.id), 1)
  tabs.splice(to, 0, current.id)
}

function endDrag(): void {
  window.clearTimeout(holdTimer)
  drag.value = null
}

// While a finger drags a tab, the row must not scroll along.
function onTabTouchMove(event: TouchEvent): void {
  if (drag.value?.active) event.preventDefault()
}

// The iframes share this page's origin, so their pointer events can be watched directly: a
// touch inside a column makes it the active one (a focus change alone could be the terminal's
// own autofocus).
function onFrameLoad(id: string): void {
  frameOf(id)?.contentWindow?.addEventListener(
    'pointerdown',
    () => {
      workspace.value.active = id
    },
    true,
  )
}

// Typing goes to the active column's input field.
watch(
  () => workspace.value.active,
  async (id) => {
    if (id === null) return
    await nextTick()
    frameOf(id)?.contentDocument?.querySelector('textarea')?.focus()
  },
)

// Opened from the agent list, or a new agent started from the "+" menu.
watch(
  () => route.query.open,
  (id) => {
    if (typeof id !== 'string') return
    open(id)
    void router.replace({ path: '/workspace' })
  },
  { immediate: true },
)
</script>

<template>
  <div class="flex h-dvh flex-col bg-slate-900">
    <header class="flex items-center gap-1 border-b border-slate-800 px-1 py-1">
      <button class="btn-icon" :aria-label="$t('terminal.back')" @click="router.push('/sessions')">
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <h1 class="flex-1 truncate font-semibold">{{ $t('nav.workspace') }}</h1>
      <div class="relative">
        <button class="btn-icon" :aria-label="$t('workspace.add')" :title="$t('workspace.add')" @click="picking = !picking">
          <AppIcon name="plus" />
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
            {{ baseName(session.path) }}
          </button>
          <p v-if="notOpen.length === 0" class="px-3 py-2 text-sm text-slate-500">{{ $t('workspace.allOpen') }}</p>
          <RouterLink :to="{ path: '/files', query: { workspace: '1' } }" class="btn-primary mt-1">
            <AppIcon name="plus" />{{ $t('sessions.startNew') }}
          </RouterLink>
        </div>
      </div>
      <div class="flex shrink-0 items-center gap-1 text-sm text-slate-400" :title="$t('workspace.columns')">
        <button class="btn-icon" :aria-label="$t('workspace.fewerColumns')" @click="changeVisible(-1)">−</button>
        <span>{{ workspace.visible }}</span>
        <button class="btn-icon" :aria-label="$t('workspace.moreColumns')" @click="changeVisible(1)">+</button>
      </div>
    </header>

    <p v-if="workspace.tabs.length === 0" class="p-6 text-center text-slate-400">{{ $t('workspace.empty') }}</p>

    <!-- One scrolling row; 100cqw is its width, so N columns fill it exactly. -->
    <div
      ref="row"
      class="min-h-0 flex-1 overflow-x-auto"
      :class="{ 'snap-x snap-mandatory': resize === null }"
      style="container-type: inline-size"
    >
      <div class="grid h-full grid-rows-[auto_minmax(0,1fr)]" :style="gridStyle">
        <div
          v-for="id in workspace.tabs"
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
          @pointerdown="onTabPointerDown($event, id)"
          @pointermove="onTabPointerMove"
          @pointerup="onTabPointerUp"
          @pointercancel="endDrag"
          @touchmove="onTabTouchMove"
          @contextmenu.prevent
        >
          <button class="min-w-0 flex-1 truncate text-left font-medium" @click="activate(id)">
            {{ tabName(id) }}
          </button>
          <button
            class="px-2 text-slate-500 hover:text-slate-200"
            :aria-label="$t('workspace.close')"
            @pointerdown.stop
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
          class="h-full w-full bg-slate-900"
          :style="{ gridColumn: column(id), gridRow: '2' }"
          allow="microphone; clipboard-write"
          @load="onFrameLoad(id)"
        />
        <!-- Divider on each column's right edge, above the iframes (which would swallow it). -->
        <div
          v-for="id in workspace.tabs"
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
