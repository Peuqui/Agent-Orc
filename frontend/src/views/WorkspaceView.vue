<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import { useSessions } from '../composables/useSessions'
import { baseName } from '../format'

// Several agents side by side: every open agent is the terminal page in its own iframe, so
// each keeps its connection, history and half-typed text while hidden in a tab.
const STORAGE_KEY = 'agent-orc-workspace'
const MIN_COLUMNS = 1

interface Workspace {
  tabs: string[]
  /** Which tab each column shows; its length is the number of columns. */
  panes: (string | null)[]
  active: number
}

const route = useRoute()
const router = useRouter()
const { sessions } = useSessions()

function loadWorkspace(): Workspace {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored ? (JSON.parse(stored) as Workspace) : { tabs: [], panes: [null], active: 0 }
}

const workspace = ref<Workspace>(loadWorkspace())
watch(workspace, (value) => localStorage.setItem(STORAGE_KEY, JSON.stringify(value)), { deep: true })

const frames = ref<HTMLIFrameElement[]>([])

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

/**
 * Show a tab: a column showing it already becomes active; otherwise it goes into the active
 * column, or, for an agent newly opened from the agent list, into an empty column first.
 */
function show(id: string, preferEmptyColumn = false): void {
  const { panes } = workspace.value
  if (!workspace.value.tabs.includes(id)) workspace.value.tabs.push(id)
  const shownIn = panes.indexOf(id)
  const empty = panes.indexOf(null)
  const column =
    shownIn !== -1 ? shownIn : preferEmptyColumn && empty !== -1 ? empty : workspace.value.active
  panes[column] = id
  workspace.value.active = column
}

function closeTab(id: string): void {
  const { tabs, panes } = workspace.value
  tabs.splice(tabs.indexOf(id), 1)
  const column = panes.indexOf(id)
  if (column !== -1) panes[column] = tabs.find((tab) => !panes.includes(tab)) ?? null
}

function changeColumns(delta: number): void {
  const { panes } = workspace.value
  if (delta > 0) panes.push(workspace.value.tabs.find((tab) => !panes.includes(tab)) ?? null)
  else if (panes.length > MIN_COLUMNS) panes.pop()
  workspace.value.active = Math.min(workspace.value.active, panes.length - 1)
}

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${workspace.value.panes.length}, minmax(0, 1fr))`,
}))

// Clicks inside an iframe never reach this page; the page only loses focus to it.
function onWindowBlur(): void {
  window.setTimeout(() => {
    const frame = frames.value.find((candidate) => candidate === document.activeElement)
    const id = frame?.dataset.tab
    if (id !== undefined) {
      const column = workspace.value.panes.indexOf(id)
      if (column !== -1) workspace.value.active = column
    }
  })
}

watch(
  () => route.query.open,
  (open) => {
    if (typeof open !== 'string') return
    show(open, true)
    void router.replace({ path: '/workspace' })
  },
  { immediate: true },
)

onMounted(() => window.addEventListener('blur', onWindowBlur))
onBeforeUnmount(() => window.removeEventListener('blur', onWindowBlur))
</script>

<template>
  <div class="flex h-dvh flex-col bg-slate-900">
    <header class="flex items-center gap-1 border-b border-slate-800 px-1 py-1">
      <button class="btn-icon" :aria-label="$t('terminal.back')" @click="router.push('/sessions')">
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <nav class="flex min-w-0 flex-1 gap-1 overflow-x-auto">
        <div
          v-for="id in workspace.tabs"
          :key="id"
          class="flex shrink-0 items-center rounded-lg border text-sm"
          :class="
            workspace.panes[workspace.active] === id
              ? 'border-red-500 bg-slate-800 text-slate-100'
              : workspace.panes.includes(id)
                ? 'border-slate-500 bg-slate-800 text-slate-200'
                : 'border-slate-700 text-slate-400'
          "
        >
          <button class="py-1 pr-1 pl-3" @click="show(id)">{{ tabName(id) }}</button>
          <button class="px-2 py-1 text-slate-500 hover:text-slate-200" :aria-label="$t('workspace.close')" @click="closeTab(id)">
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

    <div class="grid min-h-0 flex-1 gap-px bg-slate-800" :style="gridStyle">
      <iframe
        v-for="id in workspace.tabs"
        :key="id"
        ref="frames"
        :data-tab="id"
        :src="frameUrl(id)"
        :title="tabName(id)"
        class="h-full w-full border-t-2"
        :class="workspace.panes[workspace.active] === id ? 'border-red-500' : 'border-transparent'"
        :style="frameStyle(id)"
        allow="microphone; clipboard-write"
      />
      <button
        v-for="(pane, column) in workspace.panes"
        v-show="pane === null"
        :key="`empty-${column}`"
        class="flex items-center justify-center border-t-2 bg-slate-900 p-4 text-sm text-slate-500"
        :class="workspace.active === column ? 'border-red-500' : 'border-transparent'"
        :style="{ gridColumn: String(column + 1), gridRow: '1' }"
        @click="workspace.active = column"
      >
        {{ $t('workspace.empty') }}
      </button>
    </div>
  </div>
</template>
