<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { useSessions } from '../composables/useSessions'
import { baseName } from '../format'

// Several agents side by side: every open agent is the terminal page in its own iframe, so
// each keeps its connection, history and half-typed text while hidden in a tab. The iframes
// never move in the DOM (that would reload them); only their grid column changes.
const STORAGE_KEY = 'agent-orc-workspace'
const MIN_COLUMNS = 1
// A pointer moving less than this is a tap on a tab, not a drag.
const DRAG_THRESHOLD_PX = 8

interface Workspace {
  tabs: string[]
  /** Which tab each column shows; its length is the number of columns. */
  panes: (string | null)[]
  active: number
}

interface Drag {
  id: string
  pointerId: number
  startX: number
  startY: number
  active: boolean
  /** Column under the pointer, or the tab it would be put in front of (null: at the end). */
  column: number | null
  before: string | null | undefined
}

const route = useRoute()
const router = useRouter()
const { sessions, profiles } = useSessions()

function loadWorkspace(): Workspace {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored ? (JSON.parse(stored) as Workspace) : { tabs: [], panes: [null], active: 0 }
}

const workspace = ref<Workspace>(loadWorkspace())
watch(workspace, (value) => localStorage.setItem(STORAGE_KEY, JSON.stringify(value)), { deep: true })

const frames = ref<HTMLIFrameElement[]>([])
// The iframes in the order they were opened, apart from the tab order: an iframe moved in
// the DOM reloads, so sorting the tabs must never reorder them. Only appended and removed.
const frameIds = ref<string[]>([...workspace.value.tabs])
const drag = ref<Drag | null>(null)

const runningSessions = computed(() => sessions.value.filter((session) => session.running))
const labels = computed(() => new Map(profiles.value.map((profile) => [profile.name, profile.label])))

function tabName(id: string): string {
  const session = sessions.value.find((candidate) => candidate.id === id)
  return session ? baseName(session.path) : id
}

function frameUrl(id: string): string {
  return `./#/terminal/${encodeURIComponent(id)}?embedded`
}

/** Grid position of a tab's iframe: its column, or hidden when no column shows it. */
function frameStyle(id: string): Record<string, string> {
  const column = workspace.value.panes.indexOf(id)
  return column === -1 ? { display: 'none' } : { gridColumn: String(column + 1), gridRow: '1' }
}

function cell(column: number): Record<string, string> {
  return { gridColumn: String(column + 1), gridRow: '1' }
}

function addTab(id: string): void {
  if (workspace.value.tabs.includes(id)) return
  workspace.value.tabs.push(id)
  frameIds.value.push(id)
}

/** Put a tab into a column; a column that showed it before gets that column's tab instead. */
function place(id: string, column: number): void {
  const { panes } = workspace.value
  addTab(id)
  const shownIn = panes.indexOf(id)
  if (shownIn !== -1 && shownIn !== column) panes[shownIn] = panes[column]
  panes[column] = id
  workspace.value.active = column
}

/** Tap on a tab: a column showing it already becomes active, else it goes into the active one. */
function show(id: string): void {
  const shownIn = workspace.value.panes.indexOf(id)
  if (shownIn !== -1) workspace.value.active = shownIn
  else place(id, workspace.value.active)
}

function closeTab(id: string): void {
  const { tabs, panes } = workspace.value
  tabs.splice(tabs.indexOf(id), 1)
  frameIds.value.splice(frameIds.value.indexOf(id), 1)
  const column = panes.indexOf(id)
  if (column !== -1) panes[column] = null
}

function moveTab(id: string, before: string | null): void {
  const { tabs } = workspace.value
  tabs.splice(tabs.indexOf(id), 1)
  const index = before === null ? tabs.length : tabs.indexOf(before)
  tabs.splice(index, 0, id)
}

function changeColumns(delta: number): void {
  const { panes } = workspace.value
  if (delta > 0) panes.push(null)
  else if (panes.length > MIN_COLUMNS) panes.pop()
  workspace.value.active = Math.min(workspace.value.active, panes.length - 1)
}

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${workspace.value.panes.length}, minmax(0, 1fr))`,
}))

function onTabPointerDown(event: PointerEvent, id: string): void {
  if (event.button !== 0) return
  drag.value = {
    id,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    active: false,
    column: null,
    before: undefined,
  }
  // Keeps the pointer events coming while the pointer leaves the tab.
  const tab = event.currentTarget as HTMLElement
  tab.setPointerCapture(event.pointerId)
}

/** Where a dragged tab would land: a column's drop zone, or a place in the tab bar. */
function dropTarget(x: number, y: number): Pick<Drag, 'column' | 'before'> {
  for (const element of document.elementsFromPoint(x, y)) {
    if (!(element instanceof HTMLElement)) continue
    if (element.dataset.dropColumn !== undefined) {
      return { column: Number(element.dataset.dropColumn), before: undefined }
    }
    if (element.dataset.tabBar !== undefined) {
      const tabs = [...element.querySelectorAll<HTMLElement>('[data-tab-id]')]
      const next = tabs.find((tab) => {
        const box = tab.getBoundingClientRect()
        return x < box.left + box.width / 2
      })
      return { column: null, before: next?.dataset.tabId ?? null }
    }
  }
  return { column: null, before: undefined }
}

function onTabPointerMove(event: PointerEvent): void {
  const current = drag.value
  if (current === null || event.pointerId !== current.pointerId) return
  const moved = Math.hypot(event.clientX - current.startX, event.clientY - current.startY)
  if (!current.active && moved < DRAG_THRESHOLD_PX) return
  current.active = true
  Object.assign(current, dropTarget(event.clientX, event.clientY))
}

function onTabPointerUp(event: PointerEvent): void {
  const current = drag.value
  if (current === null || event.pointerId !== current.pointerId) return
  drag.value = null
  if (!current.active) show(current.id)
  else if (current.column !== null) place(current.id, current.column)
  else if (current.before !== undefined && current.before !== current.id) {
    moveTab(current.id, current.before)
  }
}

const activeTab = computed(() => workspace.value.panes[workspace.value.active])

function frameOf(id: string): HTMLIFrameElement | undefined {
  return frames.value.find((frame) => frame.dataset.tab === id)
}

// The iframes share this page's origin, so their pointer events can be watched directly: a
// touch inside a column makes it the active one (a focus change alone could be the terminal's
// own autofocus).
function onFrameLoad(id: string): void {
  frameOf(id)?.contentWindow?.addEventListener(
    'pointerdown',
    () => {
      const column = workspace.value.panes.indexOf(id)
      if (column !== -1) workspace.value.active = column
    },
    true,
  )
}

// Typing goes to the active column's input field.
watch(activeTab, async (id) => {
  if (id === null || id === undefined) return
  await nextTick()
  frameOf(id)?.contentDocument?.querySelector('textarea')?.focus()
})

// Opened from the agent list (?open=id) or for a column that asked for a new agent (&column=n).
watch(
  () => route.query,
  (query) => {
    if (typeof query.open !== 'string') return
    const column = Number(query.column)
    if (Number.isInteger(column) && column >= 0 && column < workspace.value.panes.length) {
      place(query.open, column)
    } else {
      const empty = workspace.value.panes.indexOf(null)
      place(query.open, empty !== -1 ? empty : workspace.value.active)
    }
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
      <nav data-tab-bar class="flex min-w-0 flex-1 gap-1 overflow-x-auto">
        <div
          v-for="id in workspace.tabs"
          :key="id"
          :data-tab-id="id"
          class="flex shrink-0 cursor-grab touch-none items-center rounded-lg border text-sm select-none"
          :class="[
            activeTab === id
              ? 'border-red-500 bg-slate-800 text-slate-100'
              : workspace.panes.includes(id)
                ? 'border-slate-500 bg-slate-800 text-slate-200'
                : 'border-slate-700 text-slate-400',
            drag?.active && drag.id === id ? 'opacity-50' : '',
            drag?.active && drag.column === null && drag.before === id ? 'ml-3 border-l-amber-400' : '',
          ]"
          @pointerdown="onTabPointerDown($event, id)"
          @pointermove="onTabPointerMove"
          @pointerup="onTabPointerUp"
          @pointercancel="drag = null"
        >
          <span class="py-1 pr-1 pl-3">{{ tabName(id) }}</span>
          <button
            class="px-2 py-1 text-slate-500 hover:text-slate-200"
            :aria-label="$t('workspace.close')"
            @pointerdown.stop
            @click="closeTab(id)"
          >
            ×
          </button>
        </div>
      </nav>
      <div class="flex shrink-0 items-center gap-1 text-sm text-slate-400">
        <button class="btn-icon" :aria-label="$t('workspace.fewerColumns')" @click="changeColumns(-1)">−</button>
        <span :title="$t('workspace.columns')">{{ workspace.panes.length }}</span>
        <button class="btn-icon" :aria-label="$t('workspace.moreColumns')" @click="changeColumns(1)">+</button>
      </div>
    </header>

    <div class="relative grid min-h-0 flex-1 gap-px bg-slate-800" :style="gridStyle">
      <iframe
        v-for="id in frameIds"
        :key="id"
        ref="frames"
        :data-tab="id"
        :src="frameUrl(id)"
        :title="tabName(id)"
        class="h-full w-full border-t-2"
        :data-active="activeTab === id"
        :class="activeTab === id ? 'border-red-500' : 'border-transparent'"
        :style="frameStyle(id)"
        allow="microphone; clipboard-write"
        @load="onFrameLoad(id)"
      />

      <!-- An empty column offers the running agents and a new one. -->
      <div
        v-for="(pane, column) in workspace.panes"
        v-show="pane === null"
        :key="`empty-${column}`"
        class="flex flex-col gap-2 overflow-y-auto border-t-2 bg-slate-900 p-4"
        :class="workspace.active === column ? 'border-red-500' : 'border-transparent'"
        :style="cell(column)"
        @click="workspace.active = column"
      >
        <p class="text-sm text-slate-400">{{ $t('workspace.pick') }}</p>
        <button
          v-for="session in runningSessions"
          :key="session.id"
          class="card flex flex-col items-start p-3 text-left hover:border-slate-500"
          @click.stop="place(session.id, column)"
        >
          <span class="font-semibold">{{ baseName(session.path) }}</span>
          <span class="text-xs text-slate-500">
            {{ labels.get(session.profile) ?? session.profile }}
            <template v-if="workspace.panes.includes(session.id)"> · {{ $t('workspace.shown') }}</template>
          </span>
        </button>
        <RouterLink :to="{ path: '/files', query: { column: String(column) } }" class="btn-primary">
          <AppIcon name="plus" />{{ $t('sessions.startNew') }}
        </RouterLink>
      </div>

      <!-- While a tab is dragged: drop zones over the columns (iframes would swallow the pointer). -->
      <div v-if="drag?.active" class="absolute inset-0 grid" :style="gridStyle">
        <div
          v-for="(_pane, column) in workspace.panes"
          :key="`drop-${column}`"
          :data-drop-column="column"
          class="flex items-center justify-center border-2 border-dashed text-sm"
          :class="
            drag.column === column
              ? 'border-amber-400 bg-amber-400/15 text-amber-300'
              : 'border-slate-600 bg-slate-900/60 text-slate-400'
          "
          :style="cell(column)"
        >
          {{ $t('workspace.dropHere') }}
        </div>
      </div>
    </div>
  </div>
</template>
