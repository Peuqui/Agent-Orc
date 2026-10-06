<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type Note, type Notebook } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BroadcastDialog from '../components/BroadcastDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import InputDialog from '../components/InputDialog.vue'
import { useServerEvents } from '../composables/useServerEvents'
import { useToast } from '../composables/useToast'
import { renderMarkdown } from '../markdown'

// Notebooks as tabs, each with loose notes and folders; a note is Markdown. The server keeps
// them, so every device shows the same; edits are stored shortly after the last keystroke.
const SAVE_DELAY_MS = 500
// null: the loose notes of the notebook; otherwise the index of a folder.
type FolderIndex = number | null
interface Selection {
  folder: FolderIndex
  index: number
}
type Dialog =
  | { kind: 'newNotebook' }
  | { kind: 'renameNotebook' }
  | { kind: 'deleteNotebook' }
  | { kind: 'newFolder' }
  | { kind: 'renameFolder'; folder: number }
  | { kind: 'deleteFolder'; folder: number }
  | { kind: 'deleteNote' }
  | { kind: 'send' }

const { t } = useI18n()
const toast = useToast()
const notebooks = ref<Record<string, Notebook>>({})
const current = ref<string | null>(null)
const selection = ref<Selection | null>(null)
const editing = ref(false)
const query = ref('')
const dialog = ref<Dialog | null>(null)

const names = computed(() => Object.keys(notebooks.value))
const notebook = computed(() => (current.value === null ? null : (notebooks.value[current.value] ?? null)))

function notesOf(folder: FolderIndex): Note[] {
  const book = notebook.value
  if (book === null) return []
  return folder === null ? book.notes : (book.folders[folder]?.notes ?? [])
}

const selected = computed(() => (selection.value === null ? null : (notesOf(selection.value.folder)[selection.value.index] ?? null)))
const html = computed(() => (selected.value === null ? '' : renderMarkdown(selected.value.text, '')))

interface Section {
  folder: FolderIndex
  name: string | null
  entries: { index: number; note: Note }[]
}

// What the list shows: loose notes first, then the folders; while searching only what matches.
const sections = computed<Section[]>(() => {
  const book = notebook.value
  if (book === null) return []
  const needle = query.value.trim().toLowerCase()
  const matching = (notes: Note[]) =>
    notes
      .map((note, index) => ({ index, note }))
      .filter(({ note }) => !needle || `${note.title}\n${note.text}`.toLowerCase().includes(needle))
  const all: Section[] = [
    { folder: null, name: null, entries: matching(book.notes) },
    ...book.folders.map((folder, index) => ({ folder: index, name: folder.name, entries: matching(folder.notes) })),
  ]
  return needle ? all.filter((section) => section.entries.length) : all
})

const noteCount = computed(
  () => (notebook.value?.notes.length ?? 0) + (notebook.value?.folders.reduce((sum, folder) => sum + folder.notes.length, 0) ?? 0),
)

let saveTimer: number | undefined
let saving = 0

async function flush(): Promise<void> {
  window.clearTimeout(saveTimer)
  saveTimer = undefined
  const name = current.value
  if (name === null || notebook.value === null) return
  saving++
  try {
    await api.storeNotebook(name, notebook.value)
  } catch (error) {
    toast.error(error)
  } finally {
    saving--
  }
}

function changed(): void {
  window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(flush, SAVE_DELAY_MS)
}

// Another device's change is taken over unless this one has edits of its own on the way.
async function reload(): Promise<void> {
  if (saveTimer !== undefined || saving > 0) return
  try {
    notebooks.value = await api.notebooks()
  } catch (error) {
    toast.error(error)
    return
  }
  if (current.value === null || !(current.value in notebooks.value)) {
    current.value = names.value[0] ?? null
    selection.value = null
  }
  if (selected.value === null) selection.value = null
}

useServerEvents('api/notebooks/events', reload)
onBeforeUnmount(() => void flush())

function openNotebook(name: string): void {
  void flush()
  current.value = name
  selection.value = null
  query.value = ''
}

async function createNotebook(name: string): Promise<void> {
  dialog.value = null
  if (name in notebooks.value) {
    toast.error(t('notes.exists', { name }))
    return
  }
  try {
    await api.storeNotebook(name, { notes: [], folders: [] })
  } catch (error) {
    toast.error(error)
    return
  }
  await reload()
  openNotebook(name)
}

async function renameNotebook(name: string): Promise<void> {
  dialog.value = null
  const old = current.value
  if (old === null || name === old) return
  try {
    await flush()
    await api.renameNotebook(old, name)
    current.value = name
  } catch (error) {
    toast.error(error)
  }
  await reload()
}

async function deleteNotebook(): Promise<void> {
  dialog.value = null
  const name = current.value
  if (name === null) return
  window.clearTimeout(saveTimer)
  saveTimer = undefined
  try {
    await api.deleteNotebook(name)
  } catch (error) {
    toast.error(error)
  }
  current.value = null
  selection.value = null
  await reload()
}

function addNote(): void {
  const folder = selection.value?.folder ?? null
  const notes = notesOf(folder)
  notes.push({ title: '', text: '' })
  selection.value = { folder, index: notes.length - 1 }
  editing.value = true
  changed()
}

function addFolder(name: string): void {
  dialog.value = null
  notebook.value?.folders.push({ name, notes: [] })
  changed()
}

function renameFolder(folder: number, name: string): void {
  dialog.value = null
  const target = notebook.value?.folders[folder]
  if (target) target.name = name
  changed()
}

function deleteFolder(folder: number): void {
  dialog.value = null
  notebook.value?.folders.splice(folder, 1)
  selection.value = null
  changed()
}

function deleteNote(): void {
  dialog.value = null
  if (selection.value === null) return
  notesOf(selection.value.folder).splice(selection.value.index, 1)
  selection.value = null
  changed()
}

/** Moves the selected note into a folder (null: loose), at the end. */
function moveNote(target: FolderIndex): void {
  const from = selection.value
  if (from === null || from.folder === target) return
  const [note] = notesOf(from.folder).splice(from.index, 1)
  const notes = notesOf(target)
  notes.push(note)
  selection.value = { folder: target, index: notes.length - 1 }
  changed()
}

async function copyNote(): Promise<void> {
  if (selected.value === null) return
  try {
    await navigator.clipboard.writeText(selected.value.text)
    toast.info(t('notes.copied'))
  } catch (error) {
    toast.error(error)
  }
}

// The formatting bar: each button writes the Markdown for the selection (or the line) into the
// text, so nobody has to know the syntax.
interface Edit {
  text: string
  from: number
  to: number
}
interface Format {
  id: string
  label: string
  apply: (text: string, from: number, to: number) => Edit
}

// The text put in when nothing is selected comes from the translations (notes.placeholder.<kind>).
function wrap(mark: string, kind: string): Format['apply'] {
  return (text, from, to) => {
    const inner = text.slice(from, to) || t('notes.placeholder.' + kind)
    const start = from + mark.length
    return { text: text.slice(0, from) + mark + inner + mark + text.slice(to), from: start, to: start + inner.length }
  }
}

/** Puts the prefix before every line the selection touches. */
function prefixLines(prefix: string): Format['apply'] {
  return (text, from, to) => {
    const start = text.lastIndexOf('\n', from - 1) + 1
    const nextBreak = text.indexOf('\n', to)
    const end = nextBreak === -1 ? text.length : nextBreak
    const lines = text.slice(start, end).split('\n').map((line) => prefix + line)
    const block = lines.join('\n')
    return { text: text.slice(0, start) + block + text.slice(end), from: start, to: start + block.length }
  }
}

const LINK_ADDRESS = 'https://'
const formats: Format[] = [
  { id: 'bold', label: 'B', apply: wrap('**', 'bold') },
  { id: 'italic', label: 'I', apply: wrap('*', 'italic') },
  { id: 'heading', label: 'H', apply: prefixLines('## ') },
  { id: 'list', label: '•', apply: prefixLines('- ') },
  {
    id: 'code',
    label: '</>',
    apply: (text, from, to) => {
      const chosen = text.slice(from, to)
      if (!chosen.includes('\n')) return wrap('`', 'code')(text, from, to)
      const block = '```\n' + chosen + '\n```'
      return { text: text.slice(0, from) + block + text.slice(to), from: from + 4, to: from + 4 + chosen.length }
    },
  },
  {
    id: 'link',
    label: '🔗',
    apply: (text, from, to) => {
      const label = text.slice(from, to) || t('notes.placeholder.link')
      const start = from + label.length + 3
      return {
        text: `${text.slice(0, from)}[${label}](${LINK_ADDRESS})${text.slice(to)}`,
        from: start,
        to: start + LINK_ADDRESS.length,
      }
    },
  },
]

const field = ref<HTMLTextAreaElement>()

async function format(apply: Format['apply']): Promise<void> {
  const element = field.value
  const note = selected.value
  if (!element || !note) return
  const edit = apply(note.text, element.selectionStart, element.selectionEnd)
  note.text = edit.text
  changed()
  await nextTick()
  element.focus()
  element.setSelectionRange(edit.from, edit.to)
}

function folderName(folder: number): string {
  return notebook.value?.folders[folder]?.name ?? ''
}

function firstLine(note: Note): string {
  return note.text.split('\n').find((line) => line.trim()) ?? ''
}
</script>

<template>
  <section class="flex flex-col gap-3">
    <div class="flex flex-wrap items-center gap-1.5">
      <button
        v-for="name in names"
        :key="name"
        class="btn-small"
        :class="name === current ? 'btn-primary' : 'btn-secondary'"
        @click="openNotebook(name)"
      >
        {{ name }}
      </button>
      <button class="btn-secondary btn-small-icon" :title="$t('notes.newNotebook')" :aria-label="$t('notes.newNotebook')" @click="dialog = { kind: 'newNotebook' }">
        <AppIcon name="plus" />
      </button>
      <template v-if="current !== null">
        <button class="btn-secondary btn-small-icon" :title="$t('notes.renameNotebook')" :aria-label="$t('notes.renameNotebook')" @click="dialog = { kind: 'renameNotebook' }">
          <AppIcon name="pencil" />
        </button>
        <button class="btn-secondary btn-small-icon" :title="$t('notes.deleteNotebook')" :aria-label="$t('notes.deleteNotebook')" @click="dialog = { kind: 'deleteNotebook' }">
          <AppIcon name="trash" />
        </button>
      </template>
    </div>

    <p v-if="current === null" class="text-slate-400">{{ $t('notes.empty') }}</p>

    <!-- Wide: list and note side by side; while editing the note itself has two columns (text and
         view), so below xl the list steps aside, as on phones. -->
    <div v-else class="md:grid md:grid-cols-[20rem_1fr] md:gap-4" :class="editing && selection ? 'md:max-xl:grid-cols-1' : ''">
      <div class="flex flex-col gap-3" :class="selection ? (editing ? 'max-xl:hidden' : 'max-md:hidden') : ''">
        <div class="flex gap-1.5">
          <input v-model="query" type="search" class="input flex-1 text-sm" :placeholder="$t('notes.search')" />
          <button class="btn-primary btn-small-icon" :title="$t('notes.newNote')" :aria-label="$t('notes.newNote')" @click="addNote">
            <AppIcon name="plus" />
          </button>
          <button class="btn-secondary btn-small-icon" :title="$t('notes.newFolder')" :aria-label="$t('notes.newFolder')" @click="dialog = { kind: 'newFolder' }">
            <AppIcon name="folder" />
          </button>
        </div>
        <p v-if="!noteCount" class="text-sm text-slate-500">{{ $t('notes.emptyNotebook') }}</p>
        <p v-else-if="!sections.length" class="text-sm text-slate-500">{{ $t('notes.noMatch') }}</p>
        <div v-for="section in sections" :key="section.folder ?? 'loose'" class="flex flex-col gap-1">
          <div v-if="section.folder !== null" class="flex items-center gap-1 text-sm text-slate-400">
            <AppIcon name="folder" />
            <span class="flex-1 truncate font-medium">{{ section.name }}</span>
            <button class="btn-icon" :title="$t('notes.renameFolder')" :aria-label="$t('notes.renameFolder')" @click="dialog = { kind: 'renameFolder', folder: section.folder }">
              <AppIcon name="pencil" />
            </button>
            <button class="btn-icon" :title="$t('notes.deleteFolder')" :aria-label="$t('notes.deleteFolder')" @click="dialog = { kind: 'deleteFolder', folder: section.folder }">
              <AppIcon name="trash" />
            </button>
          </div>
          <button
            v-for="entry in section.entries"
            :key="entry.index"
            class="card flex flex-col items-start px-3 py-2 text-left"
            :class="selection?.folder === section.folder && selection?.index === entry.index ? 'ring-2 ring-red-500' : ''"
            @click="(selection = { folder: section.folder, index: entry.index }), (editing = false)"
          >
            <span class="w-full truncate font-medium">{{ entry.note.title || $t('notes.untitled') }}</span>
            <span class="w-full truncate text-xs text-slate-500">{{ firstLine(entry.note) }}</span>
          </button>
        </div>
      </div>

      <div v-if="selected" class="flex min-w-0 flex-col gap-3">
        <div class="flex flex-wrap items-center gap-1.5">
          <button class="btn-secondary btn-small" :class="editing ? 'xl:hidden' : 'md:hidden'" @click="selection = null">
            <AppIcon name="up" class="-rotate-90" />{{ $t('notes.back') }}
          </button>
          <button class="btn-secondary btn-small" @click="editing = !editing">
            <AppIcon :name="editing ? 'eye' : 'pencil'" />{{ editing ? $t('notes.preview') : $t('notes.edit') }}
          </button>
          <button class="btn-secondary btn-small" @click="copyNote">
            <AppIcon name="copy" />{{ $t('notes.copy') }}
          </button>
          <button class="btn-primary btn-small" @click="dialog = { kind: 'send' }">
            <AppIcon name="send" />{{ $t('notes.send') }}
          </button>
          <select
            class="h-9 rounded-lg border border-slate-600 bg-slate-800 px-2 text-sm text-slate-200"
            :aria-label="$t('notes.folder')"
            :value="selection?.folder ?? ''"
            @change="moveNote(($event.target as HTMLSelectElement).value === '' ? null : Number(($event.target as HTMLSelectElement).value))"
          >
            <option value="">{{ $t('notes.noFolder') }}</option>
            <option v-for="(folder, index) in notebook?.folders" :key="index" :value="index">{{ folder.name }}</option>
          </select>
          <button class="btn-secondary btn-small-icon ml-auto" :title="$t('notes.deleteNote')" :aria-label="$t('notes.deleteNote')" @click="dialog = { kind: 'deleteNote' }">
            <AppIcon name="trash" />
          </button>
        </div>
        <input v-model="selected.title" class="input font-semibold" :placeholder="$t('notes.titlePlaceholder')" @input="changed" />
        <!-- Editing: text left, view right on wide screens; on phones one of them at a time. -->
        <div :class="editing ? 'md:grid md:grid-cols-2 md:gap-4' : ''">
          <div v-if="editing" class="flex min-w-0 flex-col gap-3">
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="item in formats"
                :key="item.id"
                class="btn-secondary btn-small min-w-9 justify-center"
                :class="item.id === 'bold' ? 'font-bold' : item.id === 'italic' ? 'italic' : ''"
                :title="$t('notes.format.' + item.id)"
                :aria-label="$t('notes.format.' + item.id)"
                @pointerdown.prevent
                @click="format(item.apply)"
              >
                {{ item.label }}
              </button>
            </div>
            <textarea
              ref="field"
              v-model="selected.text"
              class="input min-h-[50dvh] py-2 font-mono text-sm"
              :placeholder="$t('notes.textPlaceholder')"
              spellcheck="false"
              @input="changed"
            />
          </div>
          <div class="markdown min-w-0 min-h-[20dvh]" :class="editing ? 'max-md:hidden md:border-l md:border-slate-700 md:pl-4' : ''" v-html="html" />
        </div>
      </div>
    </div>

    <InputDialog v-if="dialog?.kind === 'newNotebook'" :title="$t('notes.newNotebook')" :label="$t('notes.name')" :submit-label="$t('notes.create')" @submit="createNotebook" @close="dialog = null" />
    <InputDialog v-if="dialog?.kind === 'renameNotebook'" :title="$t('notes.renameNotebook')" :label="$t('notes.name')" :submit-label="$t('notes.rename')" :initial-value="current ?? ''" @submit="renameNotebook" @close="dialog = null" />
    <ConfirmDialog v-if="dialog?.kind === 'deleteNotebook'" :title="$t('notes.deleteNotebook')" :message="$t('notes.confirmDeleteNotebook', { name: current })" :confirm-label="$t('notes.delete')" danger @confirm="deleteNotebook" @close="dialog = null" />
    <InputDialog v-if="dialog?.kind === 'newFolder'" :title="$t('notes.newFolder')" :label="$t('notes.name')" :submit-label="$t('notes.create')" @submit="addFolder" @close="dialog = null" />
    <InputDialog
      v-if="dialog?.kind === 'renameFolder'"
      :title="$t('notes.renameFolder')"
      :label="$t('notes.name')"
      :submit-label="$t('notes.rename')"
      :initial-value="folderName(dialog.folder)"
      @submit="(name) => dialog?.kind === 'renameFolder' && renameFolder(dialog.folder, name)"
      @close="dialog = null"
    />
    <ConfirmDialog
      v-if="dialog?.kind === 'deleteFolder'"
      :title="$t('notes.deleteFolder')"
      :message="$t('notes.confirmDeleteFolder', { name: folderName(dialog.folder), count: notesOf(dialog.folder).length })"
      :confirm-label="$t('notes.delete')"
      danger
      @confirm="deleteFolder(dialog.folder)"
      @close="dialog = null"
    />
    <ConfirmDialog v-if="dialog?.kind === 'deleteNote'" :title="$t('notes.deleteNote')" :message="$t('notes.confirmDeleteNote', { title: selected?.title || $t('notes.untitled') })" :confirm-label="$t('notes.delete')" danger @confirm="deleteNote" @close="dialog = null" />
    <BroadcastDialog v-if="dialog?.kind === 'send' && selected" :initial-text="selected.text" @close="dialog = null" />
  </section>
</template>
