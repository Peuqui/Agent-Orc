<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api, type FileEntry } from '../api'
import { draggedPaths, dragsPaths, setDraggedPaths } from '../dragTypes'
import { useFileSort } from '../composables/useFileSort'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { sortEntries } from '../fileSort'
import { baseName, formatDate, formatSize, parentPath } from '../format'
import { collect, renameTakenFolders, type UploadItem } from '../uploadTree'
import AppIcon from './AppIcon.vue'

// One view of a folder: its entries (ordered, with a checkbox each), the way up, and the area files
// and folders from the computer are dropped on to upload them. What is dragged from a list
// (the selection, or the one row) is moved into the folder it is dropped on: a folder row, or
// this folder (Ctrl copies). The page decides what is done with a selection.
const props = defineProps<{ path: string; root: string; marked: boolean }>()
const emit = defineEmits<{
  navigate: [path: string]
  activate: []
  menu: [entry: FileEntry]
  selection: [entries: FileEntry[]]
  dropped: [paths: string[], folder: string, copy: boolean]
}>()

const MILLISECONDS_PER_SECOND = 1000

const router = useRouter()
const { locale } = useI18n()
const { sort } = useFileSort()
const { sessionByPath } = useSessions()
const toast = useToast()

const entries = ref<FileEntry[]>([])
// False until the folder's listing has arrived (or failed, which is toasted): an empty list before
// that is not an empty folder.
const loaded = ref(false)
const sortedEntries = computed(() => sortEntries(entries.value, sort.value))
const selected = ref(new Set<string>())
const selectedEntries = computed(() => entries.value.filter((entry) => selected.value.has(entry.path)))
watch(selectedEntries, (chosen) => emit('selection', chosen))

const canGoUp = computed(() => props.path !== props.root && props.path.startsWith(props.root))
const relativePath = computed(() => props.path.slice(props.root.length) || baseName(props.root))

async function reload(): Promise<void> {
  if (!props.path) return
  try {
    entries.value = await api.listFiles(props.path)
  } catch (error) {
    toast.error(error)
  }
  loaded.value = true
  // What is gone (moved, trashed) is not selected any more.
  const present = new Set(entries.value.map((entry) => entry.path))
  selected.value = new Set([...selected.value].filter((path) => present.has(path)))
}

function toggle(entry: FileEntry): void {
  const next = new Set(selected.value)
  if (!next.delete(entry.path)) next.add(entry.path)
  selected.value = next
}

function selectAll(): void {
  selected.value = new Set(entries.value.map((entry) => entry.path))
}

function clearSelection(): void {
  selected.value = new Set()
}

function openEntry(entry: FileEntry): void {
  if (entry.is_dir) emit('navigate', entry.path)
  else void router.push({ path: '/edit', query: { path: entry.path } })
}

// Another folder starts at its top, not where the page was scrolled to in the one before.
watch(
  () => props.path,
  () => {
    clearSelection()
    loaded.value = false
    window.scrollTo({ top: 0 })
    void reload()
  },
)
onMounted(reload)

// Uploads: files, or whole folders with their structure, from the picker or dropped on the list,
// one after the other. A name that is taken gets a number on the server, so nothing is asked and
// nothing overwritten; a dropped folder whose name is taken becomes "name-2" (it is not mixed in).
const fileInput = ref<HTMLInputElement>()
const folderInput = ref<HTMLInputElement>()
const upload = ref<{ done: number; total: number } | null>(null)

async function uploadItems(gather: () => Promise<UploadItem[]>): Promise<void> {
  if (upload.value !== null) return
  const folder = props.path
  const progress = { done: 0, total: 0 }
  upload.value = progress
  try {
    const items = renameTakenFolders(
      await gather(),
      entries.value.map((entry) => entry.name),
    )
    progress.total = items.length
    for (const item of items) {
      if (item.file === null) await api.makeDirectory(folder, item.directory)
      else await api.uploadFile(folder, item.file, item.directory)
      progress.done += 1
    }
  } catch (error) {
    // Stops at the first one: a project that arrived in part is told at once, not buried in a list.
    toast.error(error)
  }
  upload.value = null
  await reload()
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

// What a drag over the list carries: files from the computer (upload) or paths of a list (move).
const dropping = ref<'files' | 'paths' | null>(null)
const overFolder = ref<string | null>(null)
const carriesFiles = (event: DragEvent): boolean => event.dataTransfer?.types.includes('Files') ?? false

function kindOf(event: DragEvent): 'files' | 'paths' | null {
  if (carriesFiles(event)) return 'files'
  return dragsPaths(event) ? 'paths' : null
}

function startDrag(event: DragEvent, entry: FileEntry): void {
  // A row of the selection takes the whole selection along; any other row only itself.
  setDraggedPaths(event, selected.value.has(entry.path) ? [...selected.value] : [entry.path])
}

// The drop area is the list; stopped there, so the page's own handler does not refuse it.
function onDragOver(event: DragEvent): void {
  const kind = kindOf(event)
  if (kind === null) return
  event.preventDefault()
  event.stopPropagation()
  if (event.dataTransfer) event.dataTransfer.dropEffect = event.ctrlKey ? 'copy' : kind === 'files' ? 'copy' : 'move'
  dropping.value = kind
}

function onDragLeave(event: DragEvent): void {
  if (!(event.currentTarget as Node).contains(event.relatedTarget as Node | null)) {
    dropping.value = null
    overFolder.value = null
  }
}

function onFolderDragOver(event: DragEvent, entry: FileEntry): void {
  overFolder.value = entry.is_dir && dragsPaths(event) ? entry.path : null
}

// Onto a folder row the paths go into that folder, anywhere else on the list into this one.
function onDrop(event: DragEvent): void {
  const kind = kindOf(event)
  if (kind === null) return
  event.preventDefault()
  event.stopPropagation()
  const folder = overFolder.value ?? props.path
  dropping.value = null
  overFolder.value = null
  if (kind === 'files') {
    const dropped = Array.from(event.dataTransfer?.items ?? [], (item) => item.webkitGetAsEntry())
    void uploadItems(async () =>
      (await Promise.all(dropped.filter((entry) => entry !== null).map((entry) => collect(entry, '')))).flat(),
    )
    return
  }
  const paths = draggedPaths(event)
  if (paths.length > 0) emit('dropped', paths, folder, event.ctrlKey)
}

defineExpose({ reload, clearSelection, selectAll, pickFiles: () => fileInput.value?.click(), pickFolder: () => folderInput.value?.click(), uploading: computed(() => upload.value !== null) })
</script>

<template>
  <section class="min-w-0 rounded-lg" :class="marked ? 'ring-2 ring-amber-500/60 ring-offset-4 ring-offset-slate-900' : ''" @pointerdown.capture="emit('activate')">
    <div class="mb-3 flex items-center gap-2">
      <button class="btn-icon" :disabled="!canGoUp" :aria-label="$t('files.up')" @click="emit('navigate', parentPath(path))">
        <AppIcon name="up" />
      </button>
      <h1 class="min-w-0 flex-1 truncate font-mono text-sm text-slate-300" :title="path">{{ relativePath }}</h1>
      <button v-if="entries.length > 0" class="btn-secondary btn-small shrink-0" @click="selected.size === entries.length ? clearSelection() : selectAll()">
        {{ selected.size === entries.length ? $t('files.clearSelection') : $t('files.selectAll') }}
      </button>
    </div>

    <input ref="fileInput" type="file" multiple class="hidden" @change="onFilesPicked" />
    <input ref="folderInput" type="file" webkitdirectory class="hidden" @change="onFolderPicked" />

    <p v-if="upload" class="mb-3 text-sm text-amber-300" role="status">{{ $t('files.uploading', upload) }}</p>

    <!-- The drop area: the list (and room below a short one); only it lights up. -->
    <div class="relative min-h-40" @dragover="onDragOver" @dragleave="onDragLeave" @drop="onDrop">
      <div
        v-if="dropping"
        class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-lg border-2 border-dashed border-amber-400 bg-slate-900/85 px-4 text-center text-sm text-amber-300"
        :class="overFolder ? 'opacity-0' : ''"
      >
        {{ $t(dropping === 'files' ? 'files.dropHere' : 'files.moveHere') }}
      </div>
      <p v-if="!loaded" class="card p-6 text-center text-slate-400">{{ $t('files.loading') }}</p>
      <p v-else-if="entries.length === 0" class="card p-6 text-center text-slate-400">{{ $t('files.empty') }}</p>
      <ul v-else class="card divide-y divide-slate-700">
        <li
          v-for="entry in sortedEntries"
          :key="entry.path"
          class="flex items-center"
          :class="overFolder === entry.path ? 'bg-amber-900/40' : selected.has(entry.path) ? 'bg-slate-700/40' : ''"
          draggable="true"
          @dragstart="startDrag($event, entry)"
          @dragover="onFolderDragOver($event, entry)"
          @contextmenu.prevent="emit('menu', entry)"
        >
          <label class="flex min-h-14 cursor-pointer items-center pr-1 pl-3" :title="$t('files.select', { name: entry.name })">
            <input
              type="checkbox"
              class="size-4 accent-amber-500"
              :checked="selected.has(entry.path)"
              :aria-label="$t('files.select', { name: entry.name })"
              @change="toggle(entry)"
            />
          </label>
          <button class="flex min-h-14 min-w-0 flex-1 items-center gap-3 px-3 text-left" @click="openEntry(entry)">
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
          <button class="btn-icon mr-1" :aria-label="$t('files.actions', { name: entry.name })" @click="emit('menu', entry)">
            <AppIcon name="more" />
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>
