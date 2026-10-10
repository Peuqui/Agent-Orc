<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, rawFileUrl, type FileEntry } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BaseDialog from '../components/BaseDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ConversationCleanup from '../components/ConversationCleanup.vue'
import FilePane from '../components/FilePane.vue'
import InputDialog from '../components/InputDialog.vue'
import StartAgentDialog from '../components/StartAgentDialog.vue'
import TrashPanel from '../components/TrashPanel.vue'
import { loadTabState } from '../composables/useWorkspaceTab'
import { useCopyText } from '../composables/useCopyText'
import { useFileSort } from '../composables/useFileSort'
import { useScope } from '../composables/useScope'
import { useToast } from '../composables/useToast'
import { SORT_KEYS } from '../fileSort'
import { baseName, formatCountdown } from '../format'

type Dialog =
  | { kind: 'newFolder' }
  | { kind: 'actions'; entry: FileEntry }
  | { kind: 'rename'; entry: FileEntry }
  | { kind: 'trash'; entries: FileEntry[] }
  | { kind: 'agent'; path: string }
  | { kind: 'unlock' }

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { scope, secondsLeft, load: loadScope, unlock, lock } = useScope()
const toast = useToast()
const copyText = useCopyText()
const { sort, sortBy } = useFileSort()

const dialog = ref<Dialog | null>(null)

// One view of a folder, or two side by side (a second `path2` in the address): what is selected in
// one is moved or copied into the other's folder. The buttons act on the view last clicked.
const firstPath = computed(() => {
  const queried = route.query.path
  return typeof queried === 'string' ? queried : (scope.value?.base_dir ?? '')
})
const secondPath = computed(() => (typeof route.query.path2 === 'string' ? route.query.path2 : null))
const viewPaths = computed(() => (secondPath.value === null ? [firstPath.value] : [firstPath.value, secondPath.value]))
const dual = computed(() => secondPath.value !== null)
const activeView = ref(0)
watch(dual, (isDual) => {
  if (!isDual) activeView.value = 0
})
const activePath = computed(() => viewPaths.value[activeView.value] ?? firstPath.value)
const otherPath = computed(() => (dual.value ? (viewPaths.value[1 - activeView.value] ?? null) : null))

const root = computed(() => scope.value?.root ?? '')
const unlocked = computed(() => secondsLeft.value > 0)

// Set when the workspace asked for a new agent: it opens there once started.
const forWorkspace = computed(() => route.query.workspace === '1')

function go(first: string, second: string | null): void {
  const workspace = forWorkspace.value ? '1' : undefined
  void router.push({ path: '/files', query: { path: first, path2: second ?? undefined, workspace } })
}

function navigate(view: number, path: string): void {
  go(view === 0 ? path : firstPath.value, view === 1 ? path : secondPath.value)
}

function toggleDual(): void {
  go(firstPath.value, dual.value ? null : firstPath.value)
}

const panes = ref<(InstanceType<typeof FilePane> | null)[]>([])
const selections = ref<FileEntry[][]>([[], []])
const selected = computed(() => selections.value[activeView.value] ?? [])
const trashPanel = ref<InstanceType<typeof TrashPanel>>()

async function reloadAll(): Promise<void> {
  await Promise.all(panes.value.map((pane) => pane?.reload()))
  // Something may have been trashed or restored: the trash panel shows it.
  await trashPanel.value?.load()
}

async function run(action: () => Promise<unknown>): Promise<void> {
  dialog.value = null
  try {
    await action()
  } catch (error) {
    toast.error(error)
  }
  await reloadAll()
}

function trashPaths(paths: string[]): Promise<void> {
  return run(async () => {
    for (const path of paths) await api.moveToTrash(path)
  })
}

function transfer(paths: string[], folder: string, copy: boolean): Promise<void> {
  return run(async () => {
    await api.transferFiles(paths, folder, copy)
    panes.value.forEach((pane) => pane?.clearSelection())
  })
}

function transferSelected(copy: boolean): void {
  if (otherPath.value !== null) void transfer(selected.value.map((entry) => entry.path), otherPath.value, copy)
}

async function onLock(): Promise<void> {
  await lock()
  // A folder shown may now be out of scope.
  const base = scope.value?.base_dir ?? ''
  const outside = (path: string | null): boolean => path !== null && !path.startsWith(base)
  if (outside(firstPath.value) || outside(secondPath.value)) {
    go(outside(firstPath.value) ? base : firstPath.value, outside(secondPath.value) ? base : secondPath.value)
  }
}

async function onUnlock(password: string): Promise<void> {
  try {
    await unlock(password)
    dialog.value = null
  } catch (error) {
    toast.error(error)
  }
}

// A file dropped beside the area is not opened by the browser (it would leave this page): nothing
// happens, and the pointer says so.
const carriesFiles = (event: DragEvent): boolean => event.dataTransfer?.types.includes('Files') ?? false

function refuseFileDrop(event: DragEvent): void {
  if (!carriesFiles(event)) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'none'
}

onMounted(async () => {
  window.addEventListener('dragover', refuseFileDrop)
  window.addEventListener('drop', refuseFileDrop)
  await loadScope()
})
onBeforeUnmount(() => {
  window.removeEventListener('dragover', refuseFileDrop)
  window.removeEventListener('drop', refuseFileDrop)
})

// What an agent is handed to work on: the paths as they are on this machine.
function copyPaths(paths: string[]): void {
  dialog.value = null
  void copyText(
    paths.join('\n'),
    paths.length === 1 ? t('files.pathCopied') : t('files.pathsCopied', { count: paths.length }),
  )
}

function createFolder(name: string): void {
  void run(() => api.createFolder(activePath.value, name))
}

function submitRename(name: string): void {
  const current = dialog.value
  if (current?.kind !== 'rename') return
  void run(() => api.rename(current.entry.path, name))
}

function confirmTrash(): void {
  const current = dialog.value
  if (current?.kind !== 'trash') return
  void trashPaths(current.entries.map((entry) => entry.path))
}

// From a workspace's "+": preselected is the workspace of this tab.
const defaultWorkspace = computed(() => (forWorkspace.value ? loadTabState().name : null))

// A new agent never takes the view away: the user opens its workspace when they want to.
function onAgentStarted(): void {
  dialog.value = null
  void router.push('/sessions')
}
</script>

<template>
  <!-- The files, and the trash beside them (below on a phone): a file dragged onto the trash is trashed. -->
  <section class="md:grid md:grid-cols-[minmax(0,1fr)_20rem] md:items-start md:gap-4">
    <div class="min-w-0">
      <div
        class="mb-3 flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm"
        :class="unlocked ? 'border-red-700 bg-red-950/60 text-red-200' : 'border-slate-700 text-slate-400'"
      >
        <span class="flex min-w-0 items-center gap-2" :title="scope?.base_dir">
          <AppIcon :name="unlocked ? 'unlock' : 'lock'" />
          <span class="truncate">
            <template v-if="unlocked">{{ $t('scope.unlocked', { time: formatCountdown(secondsLeft) }) }}</template>
            <template v-else>{{ baseName(scope?.base_dir ?? '') }}</template>
          </span>
        </span>
        <button v-if="unlocked" class="btn-danger min-h-9 shrink-0 whitespace-nowrap" @click="onLock">
          {{ $t('scope.lock') }}
        </button>
        <button
          v-else
          class="btn-secondary min-h-9 shrink-0 whitespace-nowrap"
          @click="scope?.password_required === false ? onUnlock('') : (dialog = { kind: 'unlock' })"
        >
          {{ $t('scope.unlock') }}
        </button>
      </div>

      <!-- They act on the view last clicked (the one marked when there are two). -->
      <div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <button class="btn-secondary" @click="dialog = { kind: 'newFolder' }">
          <AppIcon name="plus" />{{ $t('files.newFolder') }}
        </button>
        <button class="btn-secondary" :disabled="panes[activeView]?.uploading" @click="panes[activeView]?.pickFiles()">
          <AppIcon name="upload" />{{ $t('files.upload') }}
        </button>
        <button class="btn-secondary" :disabled="panes[activeView]?.uploading" @click="panes[activeView]?.pickFolder()">
          <AppIcon name="upload" />{{ $t('files.uploadFolder') }}
        </button>
        <button class="btn-secondary" :class="dual ? '!text-amber-300' : ''" :aria-pressed="dual" @click="toggleDual">
          <AppIcon name="workspace" />{{ $t(dual ? 'files.oneView' : 'files.twoViews') }}
        </button>
        <button class="btn-primary col-span-2 sm:col-span-1" @click="dialog = { kind: 'agent', path: activePath }">
          <AppIcon name="play" />{{ $t('files.startAgent') }}
        </button>
      </div>

      <div class="mb-3 flex flex-wrap items-center gap-1.5 text-sm" role="group" :aria-label="$t('files.sortBy')">
        <span class="mr-1 text-slate-500">{{ $t('files.sortBy') }}</span>
        <button
          v-for="key in SORT_KEYS"
          :key="key"
          class="btn-secondary btn-small"
          :class="sort.key === key ? '!text-amber-300' : ''"
          :aria-pressed="sort.key === key"
          @click="sortBy(key)"
        >
          {{ $t(`files.sort.${key}`) }}<span v-if="sort.key === key" aria-hidden="true">&nbsp;{{ sort.descending ? '↓' : '↑' }}</span>
        </button>
      </div>

      <!-- What is selected in the view last clicked. -->
      <div
        v-if="selected.length > 0"
        class="mb-3 flex flex-wrap items-center gap-1.5 rounded-lg border border-amber-700 bg-amber-950/30 px-3 py-2 text-sm"
        role="toolbar"
        :aria-label="$t('files.selectedCount', { count: selected.length })"
      >
        <span class="mr-2 font-medium text-amber-200">{{ $t('files.selectedCount', { count: selected.length }) }}</span>
        <button class="btn-secondary btn-small" @click="copyPaths(selected.map((entry) => entry.path))">
          <AppIcon name="copy" />{{ $t(selected.length === 1 ? 'files.copyPath' : 'files.copyPaths') }}
        </button>
        <template v-if="dual">
          <button class="btn-secondary btn-small" :title="$t('files.toOtherView')" @click="transferSelected(false)">
            {{ $t('files.moveToOther') }}
          </button>
          <button class="btn-secondary btn-small" :title="$t('files.toOtherView')" @click="transferSelected(true)">
            {{ $t('files.copyToOther') }}
          </button>
        </template>
        <button
          v-if="selected.length === 1"
          class="btn-secondary btn-small"
          @click="dialog = { kind: 'rename', entry: selected[0]! }"
        >
          <AppIcon name="pencil" />{{ $t('common.rename') }}
        </button>
        <a
          v-if="selected.length === 1 && !selected[0]!.is_dir"
          class="btn-secondary btn-small"
          :href="rawFileUrl(selected[0]!.path, true)"
        >
          <AppIcon name="download" />{{ $t('editor.download') }}
        </a>
        <button class="btn-danger btn-small" @click="dialog = { kind: 'trash', entries: selected }">
          <AppIcon name="trash" />{{ $t('files.toTrash') }}
        </button>
        <button class="btn-secondary btn-small ml-auto" @click="panes[activeView]?.clearSelection()">
          {{ $t('files.clearSelection') }}
        </button>
      </div>

      <div class="gap-4" :class="dual ? 'grid md:grid-cols-2' : ''">
        <FilePane
          v-for="(path, view) in viewPaths"
          :ref="(pane) => (panes[view] = pane as InstanceType<typeof FilePane> | null)"
          :key="view"
          :path="path"
          :root="root"
          :marked="dual && view === activeView"
          @activate="activeView = view"
          @navigate="(target) => navigate(view, target)"
          @menu="(entry) => (dialog = { kind: 'actions', entry })"
          @selection="(entries) => (selections[view] = entries)"
          @dropped="(paths, folder, copy) => transfer(paths, folder, copy)"
        />
      </div>
    </div>

    <aside class="mt-4 md:mt-0">
      <TrashPanel ref="trashPanel" @trash="trashPaths" @restored="reloadAll" />
      <ConversationCleanup />
    </aside>

    <BaseDialog v-if="dialog?.kind === 'actions'" :title="dialog.entry.name" @close="dialog = null">
      <div class="flex flex-col gap-2">
        <button
          v-if="dialog.entry.is_dir"
          class="btn-primary"
          @click="dialog = { kind: 'agent', path: dialog.entry.path }"
        >
          <AppIcon name="play" />{{ $t('files.startAgent') }}
        </button>
        <a v-if="!dialog.entry.is_dir" class="btn-secondary" :href="rawFileUrl(dialog.entry.path, true)">
          <AppIcon name="download" />{{ $t('editor.download') }}
        </a>
        <button class="btn-secondary" @click="copyPaths([dialog.entry.path])">
          <AppIcon name="copy" />{{ $t('files.copyPath') }}
        </button>
        <button class="btn-secondary" @click="dialog = { kind: 'rename', entry: dialog.entry }">
          <AppIcon name="pencil" />{{ $t('common.rename') }}
        </button>
        <button class="btn-danger" @click="dialog = { kind: 'trash', entries: [dialog.entry] }">
          <AppIcon name="trash" />{{ $t('files.toTrash') }}
        </button>
        <button class="btn" @click="dialog = null">{{ $t('common.cancel') }}</button>
      </div>
    </BaseDialog>

    <InputDialog
      v-if="dialog?.kind === 'newFolder'"
      :title="$t('files.newFolder')"
      :label="$t('files.folderName')"
      :submit-label="$t('common.create')"
      @submit="createFolder"
      @close="dialog = null"
    />
    <InputDialog
      v-if="dialog?.kind === 'rename'"
      :title="$t('common.rename')"
      :label="$t('files.newName')"
      :submit-label="$t('common.rename')"
      :initial-value="dialog.entry.name"
      @submit="submitRename"
      @close="dialog = null"
    />
    <ConfirmDialog
      v-if="dialog?.kind === 'trash'"
      :title="$t('files.toTrash')"
      :message="
        dialog.entries.length === 1
          ? $t('files.confirmTrash', { name: dialog.entries[0]!.name })
          : $t('files.confirmTrashMany', { count: dialog.entries.length })
      "
      :confirm-label="$t('files.toTrash')"
      danger
      @confirm="confirmTrash"
      @close="dialog = null"
    />
    <StartAgentDialog
      v-if="dialog?.kind === 'agent'"
      :path="dialog.path"
      :default-workspace="defaultWorkspace"
      @started="onAgentStarted"
      @close="dialog = null"
    />
    <InputDialog
      v-if="dialog?.kind === 'unlock'"
      :title="$t('scope.unlockTitle')"
      :hint="t('scope.unlockHint', { minutes: scope?.unlock_minutes })"
      :label="$t('login.password')"
      :submit-label="$t('common.confirm')"
      password
      @submit="onUnlock"
      @close="dialog = null"
    />
  </section>
</template>
