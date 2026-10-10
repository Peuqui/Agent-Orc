<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, rawFileUrl, type FileEntry } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BaseDialog from '../components/BaseDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import InputDialog from '../components/InputDialog.vue'
import StartAgentDialog from '../components/StartAgentDialog.vue'
import ConversationCleanup from '../components/ConversationCleanup.vue'
import TrashPanel from '../components/TrashPanel.vue'
import { DRAG_PATH_TYPE } from '../dragTypes'
import { loadTabState } from '../composables/useWorkspaceTab'
import { useScope } from '../composables/useScope'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName, formatCountdown, formatDate, formatSize, parentPath } from '../format'
import { SORT_KEYS, clicked, formatSort, parseSort, sortEntries, type SortKey } from '../fileSort'
import { collect, renameTakenFolders, type UploadItem } from '../uploadTree'

type Dialog =
  | { kind: 'newFolder' }
  | { kind: 'actions'; entry: FileEntry }
  | { kind: 'rename'; entry: FileEntry }
  | { kind: 'trash'; entry: FileEntry }
  | { kind: 'agent'; path: string }
  | { kind: 'unlock' }

const MILLISECONDS_PER_SECOND = 1000

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()
const { scope, secondsLeft, load: loadScope, unlock, lock } = useScope()
const { sessionByPath } = useSessions()
const toast = useToast()

const entries = ref<FileEntry[]>([])

// How the list is ordered, kept in this browser.
const SORT_STORAGE_KEY = 'agent-orc-files-sort'
const sort = ref(parseSort(localStorage.getItem(SORT_STORAGE_KEY)))
const sortedEntries = computed(() => sortEntries(entries.value, sort.value))

function sortBy(key: SortKey): void {
  sort.value = clicked(sort.value, key)
  localStorage.setItem(SORT_STORAGE_KEY, formatSort(sort.value))
}
const dialog = ref<Dialog | null>(null)

const currentPath = computed(() => {
  const queried = route.query.path
  return typeof queried === 'string' ? queried : (scope.value?.base_dir ?? '')
})
const root = computed(() => scope.value?.root ?? '')
const canGoUp = computed(() => currentPath.value !== root.value && currentPath.value.startsWith(root.value))
const relativePath = computed(() => currentPath.value.slice(root.value.length) || '/')
const unlocked = computed(() => secondsLeft.value > 0)

async function loadEntries(): Promise<void> {
  if (!currentPath.value) return
  try {
    entries.value = await api.listFiles(currentPath.value)
  } catch (error) {
    toast.error(error)
  }
}

// Set when the workspace asked for a new agent: it opens there once started.
const forWorkspace = computed(() => route.query.workspace === '1')

function open(path: string): void {
  const workspace = forWorkspace.value ? '1' : undefined
  void router.push({ path: '/files', query: { path, workspace } })
}

function edit(path: string): void {
  void router.push({ path: '/edit', query: { path } })
}

const trashPanel = ref<InstanceType<typeof TrashPanel>>()

async function run(action: () => Promise<unknown>): Promise<void> {
  dialog.value = null
  try {
    await action()
  } catch (error) {
    toast.error(error)
  }
  await loadEntries()
  // Something may have been trashed or restored: the trash panel shows it.
  await trashPanel.value?.load()
}

function trashDropped(path: string): Promise<void> {
  return run(() => api.moveToTrash(path))
}

function startDrag(event: DragEvent, entry: FileEntry): void {
  event.dataTransfer?.setData(DRAG_PATH_TYPE, entry.path)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

async function onLock(): Promise<void> {
  await lock()
  // The current folder may now be out of scope.
  if (!currentPath.value.startsWith(scope.value?.base_dir ?? '')) open(scope.value?.base_dir ?? '')
}

async function onUnlock(password: string): Promise<void> {
  try {
    await unlock(password)
    dialog.value = null
  } catch (error) {
    toast.error(error)
  }
}

// Uploads: files, or whole folders with their structure, from the picker or dropped on the list,
// one after the other. A name that is taken gets a number on the server, so nothing is asked and
// nothing overwritten; a dropped folder whose name is taken becomes "name-2" (it is not mixed in).
const fileInput = ref<HTMLInputElement>()
const folderInput = ref<HTMLInputElement>()
const upload = ref<{ done: number; total: number } | null>(null)
const dropping = ref(false)

async function uploadItems(gather: () => Promise<UploadItem[]>): Promise<void> {
  if (upload.value !== null) return
  const folder = currentPath.value
  const progress = { done: 0, total: 0 }
  upload.value = progress
  try {
    const items = renameTakenFolders(
      await gather(),
      entries.value.map((entry) => entry.name),
    )
    progress.total = items.length
    for (const item of items) {
      await api.uploadFile(folder, item.file, item.directory)
      progress.done += 1
    }
  } catch (error) {
    // Stops at the first one: a project that arrived in part is told at once, not buried in a list.
    toast.error(error)
  }
  upload.value = null
  await loadEntries()
}

function onFilesPicked(event: Event): void {
  const input = event.target as HTMLInputElement
  const chosen = Array.from(input.files ?? [])
  input.value = ''
  void uploadItems(async () => chosen.map((file) => ({ file, directory: '' })))
}

function onFolderPicked(event: Event): void {
  const input = event.target as HTMLInputElement
  const chosen = Array.from(input.files ?? [])
  input.value = ''
  // "folder/sub/file.txt": the folder it lies in is all but the last part.
  void uploadItems(async () =>
    chosen.map((file) => ({ file, directory: file.webkitRelativePath.split('/').slice(0, -1).join('/') })),
  )
}

// Only files from the computer: what the list drags itself (to the trash) is not meant.
const carriesFiles = (event: DragEvent): boolean => event.dataTransfer?.types.includes('Files') ?? false

// The drop area is the list; stopped there, so the page's own handler (below) does not refuse it.
function onDragOver(event: DragEvent): void {
  if (!carriesFiles(event)) return
  event.preventDefault()
  event.stopPropagation()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
  dropping.value = true
}

function onDragLeave(event: DragEvent): void {
  if (!(event.currentTarget as Node).contains(event.relatedTarget as Node | null)) dropping.value = false
}

function onDrop(event: DragEvent): void {
  if (!carriesFiles(event)) return
  event.preventDefault()
  event.stopPropagation()
  dropping.value = false
  // Taken now: the dropped entries are gone once the event is over.
  const dropped = Array.from(event.dataTransfer?.items ?? [], (item) => item.webkitGetAsEntry())
  void uploadItems(async () =>
    (await Promise.all(dropped.filter((entry) => entry !== null).map((entry) => collect(entry, '')))).flat(),
  )
}

// A file dropped beside the area is not opened by the browser (it would leave this page): nothing
// happens, and the pointer says so.
function refuseFileDrop(event: DragEvent): void {
  if (!carriesFiles(event)) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'none'
}

onMounted(() => {
  window.addEventListener('dragover', refuseFileDrop)
  window.addEventListener('drop', refuseFileDrop)
})
onBeforeUnmount(() => {
  window.removeEventListener('dragover', refuseFileDrop)
  window.removeEventListener('drop', refuseFileDrop)
})

function createFolder(name: string): void {
  void run(() => api.createFolder(currentPath.value, name))
}

function submitRename(name: string): void {
  const current = dialog.value
  if (current?.kind !== 'rename') return
  void run(() => api.rename(current.entry.path, name))
}

function confirmTrash(): void {
  const current = dialog.value
  if (current?.kind !== 'trash') return
  void run(() => api.moveToTrash(current.entry.path))
}

// From a workspace's "+": preselected is the workspace of this tab.
const defaultWorkspace = computed(() => (forWorkspace.value ? loadTabState().name : null))

// A new agent never takes the view away: the user opens its workspace when they want to.
function onAgentStarted(): void {
  dialog.value = null
  void router.push('/sessions')
}

onMounted(async () => {
  await loadScope()
  await loadEntries()
})
// Another folder starts at its top, not where the page was scrolled to in the one before.
watch(currentPath, () => {
  window.scrollTo({ top: 0 })
  void loadEntries()
})
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

    <div class="mb-3 flex items-center gap-2">
      <button class="btn-icon" :disabled="!canGoUp" :aria-label="$t('files.up')" @click="open(parentPath(currentPath))">
        <AppIcon name="up" />
      </button>
      <h1 class="min-w-0 flex-1 truncate font-mono text-sm text-slate-300">{{ relativePath }}</h1>
    </div>

    <div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
      <button class="btn-secondary" @click="dialog = { kind: 'newFolder' }">
        <AppIcon name="plus" />{{ $t('files.newFolder') }}
      </button>
      <button class="btn-secondary" :disabled="upload !== null" @click="fileInput?.click()">
        <AppIcon name="upload" />{{ $t('files.upload') }}
      </button>
      <input ref="fileInput" type="file" multiple class="hidden" @change="onFilesPicked" />
      <button class="btn-secondary" :disabled="upload !== null" @click="folderInput?.click()">
        <AppIcon name="upload" />{{ $t('files.uploadFolder') }}
      </button>
      <input ref="folderInput" type="file" webkitdirectory class="hidden" @change="onFolderPicked" />
      <button class="btn-primary" @click="dialog = { kind: 'agent', path: currentPath }">
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

    <p v-if="upload" class="mb-3 text-sm text-amber-300" role="status">{{ $t('files.uploading', upload) }}</p>

    <!-- The drop area: the list (and room below a short one); only it lights up. -->
    <div class="relative min-h-40" @dragover="onDragOver" @dragleave="onDragLeave" @drop="onDrop">
    <div
      v-if="dropping"
      class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-lg border-2 border-dashed border-amber-400 bg-slate-900/85 px-4 text-center text-sm text-amber-300"
    >
      {{ $t('files.dropHere') }}
    </div>
    <p v-if="entries.length === 0" class="card p-6 text-center text-slate-400">{{ $t('files.empty') }}</p>
    <ul v-else class="card divide-y divide-slate-700">
      <li
        v-for="entry in sortedEntries"
        :key="entry.path"
        class="flex items-center"
        draggable="true"
        @dragstart="startDrag($event, entry)"
      >
        <button
          class="flex min-h-14 min-w-0 flex-1 items-center gap-3 px-4 text-left"
          @click="entry.is_dir ? open(entry.path) : edit(entry.path)"
        >
          <AppIcon :name="entry.is_dir ? 'folder' : 'file'" :class="entry.is_dir ? 'text-red-400' : 'text-slate-500'" />
          <span class="min-w-0 flex-1">
            <span class="block truncate">{{ entry.name }}</span>
            <span class="block text-xs text-slate-500">
              <template v-if="sessionByPath.has(entry.path)">
                <span class="font-medium text-red-400">● {{ $t('files.agentRunning') }}</span>
              </template>
              <template v-else>
                {{ formatDate(new Date(entry.modified * MILLISECONDS_PER_SECOND), locale) }}
                <template v-if="!entry.is_dir"> · {{ formatSize(entry.size) }}</template>
              </template>
            </span>
          </span>
        </button>
        <button
          class="btn-icon mr-1"
          :aria-label="$t('files.actions', { name: entry.name })"
          @click="dialog = { kind: 'actions', entry }"
        >
          <AppIcon name="more" />
        </button>
      </li>
    </ul>
    </div>
    </div>

    <aside class="mt-4 md:mt-0">
      <TrashPanel ref="trashPanel" @trash="trashDropped" @restored="loadEntries" />
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
        <button class="btn-secondary" @click="dialog = { kind: 'rename', entry: dialog.entry }">
          <AppIcon name="pencil" />{{ $t('common.rename') }}
        </button>
        <button class="btn-danger" @click="dialog = { kind: 'trash', entry: dialog.entry }">
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
      :message="$t('files.confirmTrash', { name: dialog.entry.name })"
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
