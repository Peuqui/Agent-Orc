<script lang="ts">
// Per browser tab (the page's module lives as long as the tab): where each workspace's row was
// scrolled to, by workspace name (null: the unnamed one).
const scrollPositions = new Map<string | null, number>()
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { unreadTexts } from '../answers'
import {
  COLUMN_CLOSE_EVENT,
  COLUMN_FULLSCREEN_EVENT,
  COLUMN_SWIPE_EVENT,
  MESSAGE_FIELD_SELECTOR,
} from '../columns'
import AddColumnMenu from '../components/AddColumnMenu.vue'
import AppIcon from '../components/AppIcon.vue'
import ColumnCountControl from '../components/ColumnCountControl.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import HelpButton from '../components/HelpButton.vue'
import HostSwitcher from '../components/HostSwitcher.vue'
import SectionNav from '../components/SectionNav.vue'
import QuotaPanel from '../components/QuotaPanel.vue'
import SettingsMenu from '../components/SettingsMenu.vue'
import WorkspaceSwitcher from '../components/WorkspaceSwitcher.vue'
import { markSeen, seenUntil } from '../composables/useAnswerSeen'
import { useColumnWidths } from '../composables/useColumnWidths'
import { readAnswersAll } from '../composables/useSettings'
import { moveInList, useReorder } from '../composables/useReorder'
import { shownAgents } from '../composables/useShownAgents'
import { type Speakable, useSpeech } from '../composables/useSpeech'
import { sessionName, useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { useWorkspaceKeys } from '../composables/useWorkspaceKeys'
import { useWorkspaceStore } from '../composables/useWorkspaceStore'
import { WORKSPACE_DROP } from '../composables/useWorkspaceTab'
import { PHONE_WIDTH, TABS_WIDTH, TOUCH_FIRST } from '../device'

// Several agents side by side. Every open agent is one column: its tab is the head of that
// column, both in one grid, so tab order and column order can never differ. The user picks
// how many columns fill the screen; further ones follow to the right (horizontal scrolling).
// Each column is the terminal page in an iframe; the iframes never move in the DOM (that
// would reload them), only their grid column changes. Loading and storing the workspace is
// useWorkspaceStore's, the widths useColumnWidths', the header's parts are components.

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const { sessions } = useSessions()

const frames = ref<HTMLIFrameElement[]>([])
const heads = ref<HTMLElement[]>([])
const row = ref<HTMLElement>()

// On a phone one column fills the screen and a sideways swipe brings the next; the columns
// and widths set on a computer stay as they are for it.
const phone = ref(PHONE_WIDTH.matches)
const followPhoneWidth = (event: MediaQueryListEvent): void => {
  phone.value = event.matches
}
PHONE_WIDTH.addEventListener('change', followPhoneWidth)
onBeforeUnmount(() => PHONE_WIDTH.removeEventListener('change', followPhoneWidth))

// The divider being dragged holds storing back (created below, asked only later).
const store = useWorkspaceStore({ paused: () => widths.resize.value !== null, afterLoad: showRequested })
const { name, nameInput, workspace, ready, loaded, frameIds, otherTabs, workspaceOrder } = store
const widths = useColumnWidths(workspace, phone, row)
// A divider is stored once it is let go.
watch(widths.resize, store.persist)

const candidates = computed(() =>
  sessions.value
    .filter((session) => session.running && !workspace.value.tabs.includes(session.id))
    .map((session) => ({ session, livesIn: store.livesElsewhere(session.id) })),
)

// The columns in view show their agents' requests themselves (on a phone only the active one is
// in view); the announcement at the top is for the agents of other workspaces.
const agentsInView = computed(() => {
  const { active, tabs } = workspace.value
  if (!phone.value) return tabs
  return active === null ? [] : [active]
})
watch(agentsInView, (ids) => (shownAgents.value = [...ids]), { immediate: true })
onBeforeUnmount(() => (shownAgents.value = []))
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

const speech = useSpeech()
// The latest requests of each column looked at for what is new.
const NEW_ANSWERS_TURNS = 10

/** Reads the answers of this workspace's columns that were not seen yet, one column after the other. */
async function readNewAnswers(): Promise<void> {
  if (speech.playing.value !== null) return speech.stop()
  const items: Speakable[] = []
  const seen: Record<string, string> = {}
  try {
    for (const id of workspace.value.tabs) {
      const texts = unreadTexts(await api.answers(id, NEW_ANSWERS_TURNS), readAnswersAll(id), seenUntil(id))
      items.push(...texts.map((text) => ({ id: text.id, text: text.text, label: tabName(id) })))
      if (texts.length) seen[id] = texts[texts.length - 1].time
    }
  } catch (error) {
    toast.error(error)
    return
  }
  if (!items.length) return toast.info(t('answers.nothingNew'))
  for (const [id, time] of Object.entries(seen)) markSeen(id, time)
  await speech.play(items)
}

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

/** What typing goes to in a column: the message field of an agent's terminal page (see
 * MESSAGE_FIELD_ATTRIBUTE), the terminal itself in a plain terminal. */
function inputOf(id: string): HTMLElement | null | undefined {
  const document = frameOf(id)?.contentDocument
  const plainTerminal = sessions.value.find((session) => session.id === id)?.terminal
  return document?.querySelector<HTMLElement>(plainTerminal ? '.xterm-helper-textarea' : MESSAGE_FIELD_SELECTOR)
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
  store.addTab(id, after)
  void activate(id)
}

// Sorting: a whole tab is dragged and takes the place of the tab it is dropped on; the columns
// follow, as they belong to the same grid. Only the horizontal position counts, so the pointer
// may stray off the tab row. Dropped on another workspace's tab in the header, the agent moves
// to that workspace. A moved column becomes the active one and comes into view, also when it
// went to the far end of a row wider than the screen.
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
      void activate(id)
    }
  },
  ignore: '[data-no-drag]',
})
const drag = reorder.drag
const dropTarget = computed(() => (drag.value?.active ? drag.value.target : null))

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

const onShortcut = useWorkspaceKeys({
  tabs: () => workspace.value.tabs,
  order: () => workspaceOrder.value,
  name: () => name.value,
  goToColumn: (id) => void activate(id).then(() => inputOf(id)?.focus()),
})

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
  // A click in the active column (on one of its buttons, say) leaves the focus on what was
  // clicked; typing goes to the column's message field, as when the column becomes active.
  // Not where the click was meant for typing, text is marked, a dialog is open, or on touch
  // screens (the on-screen keyboard would rise).
  frameWindow?.addEventListener('click', (event) => {
    if (TOUCH_FIRST.matches || workspace.value.active !== id) return
    const target = event.target instanceof Element ? event.target : null
    if (target?.closest('input, textarea, select, [contenteditable]')) return
    if (frameWindow.getSelection()?.isCollapsed === false) return
    if (frameWindow.document.querySelector('[data-modal]')) return
    // A plain terminal keeps the focus where it was clicked.
    if (sessions.value.find((session) => session.id === id)?.terminal) return
    window.setTimeout(() => inputOf(id)?.focus(), 0)
  })
  frameWindow?.addEventListener('keydown', onShortcut, true)
  // A sideways swipe in any terminal moves the columns: phones bring the neighbouring column,
  // wider screens scroll the row to the next column start.
  frameWindow?.addEventListener(COLUMN_SWIPE_EVENT, (event) => {
    const direction = (event as CustomEvent<1 | -1>).detail
    if (!phone.value) return scrollColumns(direction)
    const neighbour = workspace.value.tabs[workspace.value.tabs.indexOf(id) + direction]
    if (neighbour !== undefined) void activate(neighbour)
  })
  frameWindow?.addEventListener(COLUMN_CLOSE_EVENT, () => store.removeTab(id))
  // A column loaded later (or reloaded) learns the current state.
  tellColumns(frameOf(id))
}

// Turning the device changes how many columns fit; the active one (the red one) stays in view,
// not the one that happened to be there before. Done at once, as the layout has changed.
watch(phone, showActiveColumn)

// Typing goes to the active column's input field; not on touch screens, where the focus would
// open the on-screen keyboard (a tap into the field does).
watch(
  () => workspace.value.active,
  async (id) => {
    if (id === null || TOUCH_FIRST.matches) return
    await nextTick()
    inputOf(id)?.focus()
  },
)

// Opened from the agent list, or a new agent started from the "+" menu.
function openRequested(): void {
  const id = route.query.open
  if (typeof id !== 'string') return
  const after = route.query.after
  open(id, typeof after === 'string' ? after : null)
  store.showName()
}

watch(() => route.query.open, () => ready.value && openRequested())

/** After loading: the column asked for in the address, else where this workspace was left in
 * this browser tab, else the active column. */
async function showRequested(): Promise<void> {
  if (typeof route.query.open === 'string') openRequested()
  else {
    store.showName()
    const left = scrollPositions.get(store.name.value)
    if (left === undefined) await showActiveColumn()
    else {
      await nextTick()
      row.value?.scrollTo({ left, behavior: 'instant' })
    }
  }
}

/** Where the row of each workspace was scrolled to; only while it is shown (switching empties
 * the row first, which scrolls it back to the start). */
function rememberScroll(): void {
  if (store.ready.value && row.value) scrollPositions.set(store.name.value, row.value.scrollLeft)
}

/** A freshly loaded workspace starts at its first column; on phones, where one column fills
 * the screen, the active one (the one left last) is brought into view instead. */
async function showActiveColumn(): Promise<void> {
  const id = workspace.value.active
  if (id === null) return
  await nextTick()
  frameOf(id)?.scrollIntoView({ behavior: 'instant', inline: phone.value ? 'start' : 'nearest', block: 'nearest' })
}

const deleting = ref(false)

function deleteThis(): void {
  deleting.value = false
  void store.deleteWorkspace()
}
</script>

<template>
  <!-- Shown once the workspaces have arrived, so nothing flashes up that is replaced a moment later. -->
  <div class="flex h-full flex-col bg-slate-900">
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
        <!-- No bottom bar in full screen: home is the agents page, the other pages are one tap on. -->
        <RouterLink to="/sessions" class="btn-icon" :aria-label="$t('nav.home')" :title="$t('nav.home')">
          <AppIcon name="home" />
        </RouterLink>
        <WorkspaceSwitcher
          v-model="nameInput"
          :name="name"
          :order="workspaceOrder"
          :other-tabs="otherTabs"
          :phone="phone"
          :tabs-in-header="tabsInHeader"
          :drop-target="dropTarget"
          @rename="store.rename"
          @delete="deleting = true"
        />
        <!-- On a wide screen the other pages are one click away (the same sections as the header's
             tabs, as icons here: the room is for the columns), not only by way of home. -->
        <SectionNav compact class="hidden xl:flex" />
        <!-- Claude's usage, centred in the room between the workspaces and the buttons; it shrinks
             with the window. Not on phones: the name gets the room (the overview shows it). -->
        <QuotaPanel v-if="!phone" class="min-w-0 flex-1 overflow-hidden sm:px-3" />
        <AddColumnMenu :candidates="candidates" @open="open" />
        <ColumnCountControl
          v-if="!phone"
          :visible="workspace.visible"
          :resized="Object.keys(workspace.widths).length > 0"
          @change="widths.changeVisible"
          @reset="widths.resetWidths"
        />
        <button
          v-if="speech.available.value"
          class="btn-icon"
          :class="speech.playing.value !== null ? 'animate-pulse text-red-400' : ''"
          :aria-label="speech.playing.value !== null ? $t('answers.stop') : $t('answers.readNewColumns')"
          :title="speech.playing.value !== null ? $t('answers.stop') : $t('answers.readNewColumns')"
          @click="readNewAnswers"
        >
          <AppIcon :name="speech.playing.value !== null ? 'stop' : 'speaker'" />
        </button>
        <button class="btn-icon" :aria-label="$t('workspace.fullscreen')" :title="$t('workspace.fullscreen')" @click="fullscreen = true">
          <AppIcon name="expand" />
        </button>
        <!-- Which machine's workspaces: the same menu as in every other page's header. -->
        <HostSwitcher />
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
        @scroll.passive="rememberScroll"
        :class="{ 'snap-x snap-mandatory': widths.resize.value === null, '[scrollbar-width:none]': phone }"
        style="container-type: inline-size"
      >
        <div class="grid h-full grid-rows-[auto_minmax(0,1fr)]" :style="widths.gridStyle.value">
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
              @click="store.removeTab(id)"
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
            :class="{ 'bg-red-500/40': widths.resize.value?.id === id }"
            :style="{ gridColumn: column(id), gridRow: '1 / span 2' }"
            :title="$t('workspace.resize')"
            @pointerdown="widths.onDividerPointerDown($event, id)"
            @pointermove="widths.onDividerPointerMove"
            @pointerup="widths.endResize"
            @pointercancel="widths.endResize"
            @dblclick="widths.resetWidth(id)"
          />
        </div>
      </div>
    </template>
  </div>
</template>
