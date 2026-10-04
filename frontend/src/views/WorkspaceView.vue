<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, type Workspace } from '../api'
import AppIcon from '../components/AppIcon.vue'
import { moveInList, useReorder } from '../composables/useReorder'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import {
  emptyWorkspace,
  loadTabState,
  MIN_VISIBLE,
  nameWindow,
  openWorkspaceTab,
  ownTabs,
  saveTabState,
  switchWorkspace,
} from '../composables/useWorkspaceTab'
import { baseName } from '../format'

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
const switching = ref(false)
const otherNames = computed(() => savedNames.value.filter((saved) => saved !== name.value).sort())

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

/** Store the workspace where it lives; a divider is stored once it is let go. */
function persist(): void {
  if (!ready.value || resize.value !== null) return
  if (name.value === null) tabState.unnamed = workspace.value
  else void api.storeWorkspace(name.value, workspace.value).catch(toast.error)
  tabState.name = name.value
  saveTabState(tabState)
  nameWindow(name.value)
}

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
  open(id)
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

/** From the switcher: another workspace in this window. */
function switchTo(other: string | null): void {
  switching.value = false
  switchWorkspace(router, other)
}

function openInOwnTab(other: string | null): void {
  switching.value = false
  openWorkspaceTab(router, other)
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
  if (current === null) tabState.unnamed = emptyWorkspace()
  persist()
  showName()
}
</script>

<template>
  <div class="flex h-dvh flex-col bg-slate-900">
    <header class="flex items-center gap-1 border-b border-slate-800 px-1 py-1">
      <button class="btn-icon" :aria-label="$t('terminal.back')" @click="router.push('/sessions')">
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <input
        v-model="nameInput"
        class="min-w-0 flex-1 rounded-md bg-transparent px-2 py-1 font-semibold placeholder:font-normal placeholder:text-slate-500 hover:bg-slate-800 focus:bg-slate-800 focus:outline-none"
        :placeholder="$t('workspace.unnamed')"
        :title="$t('workspace.nameHint')"
        :aria-label="$t('workspace.nameHint')"
        enterkeyhint="done"
        @keydown.enter="($event.target as HTMLInputElement).blur()"
        @change="rename"
      />
      <div class="relative">
        <button
          class="btn-icon"
          :aria-label="$t('workspace.switch')"
          :title="$t('workspace.switch')"
          @click="switching = !switching"
        >
          <AppIcon name="chevron" />
        </button>
        <div
          v-if="switching"
          class="card absolute top-full right-0 z-20 mt-1 flex w-64 flex-col gap-1 p-2 shadow-xl"
        >
          <div v-for="other in otherNames" :key="other" class="flex items-center rounded-md hover:bg-slate-700">
            <button class="flex min-w-0 flex-1 items-center gap-2 px-3 py-2 text-left" @click="switchTo(other)">
              <AppIcon name="workspace" /><span class="truncate">{{ other }}</span>
            </button>
            <button
              v-if="ownTabs"
              class="px-3 py-2 text-slate-400 hover:text-slate-100"
              :aria-label="$t('workspace.openInTab')"
              :title="$t('workspace.openInTab')"
              @click="openInOwnTab(other)"
            >
              <AppIcon name="external" />
            </button>
          </div>
          <p v-if="otherNames.length === 0" class="px-3 py-2 text-sm text-slate-500">{{ $t('workspace.noOthers') }}</p>
          <button class="btn-secondary mt-1" @click="ownTabs ? openInOwnTab(null) : switchTo(null)">
            <AppIcon name="plus" />{{ $t('workspace.new') }}
          </button>
        </div>
      </div>
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

    <p v-if="ready && workspace.tabs.length === 0" class="p-6 text-center text-slate-400">{{ $t('workspace.empty') }}</p>

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
          @pointerdown="reorder.onPointerDown($event, id)"
          @pointermove="reorder.onPointerMove"
          @pointerup="reorder.onPointerUp"
          @pointercancel="reorder.cancel"
          @touchmove="reorder.onTouchMove"
          @contextmenu.prevent
        >
          <button class="min-w-0 flex-1 truncate text-left font-medium" @click="activate(id)">
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
