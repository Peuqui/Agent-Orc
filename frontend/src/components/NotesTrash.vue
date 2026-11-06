<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type Note, type NoteFolder, type NotesTrashEntry } from '../api'
import { useToast } from '../composables/useToast'
import { formatDate } from '../format'
import AppIcon from './AppIcon.vue'
import ConfirmDialog from './ConfirmDialog.vue'

// What was deleted from the notebooks (a notebook, a folder, a note): restore it or delete it for
// good; only the user empties it. The page loads the entries (they change with the notebooks) and
// opens the notebook something went back into (`restored`).
type Dialog = { kind: 'delete'; entry: NotesTrashEntry } | { kind: 'empty' }

const props = defineProps<{ entries: NotesTrashEntry[]; notebooks: string[] }>()
const emit = defineEmits<{ restored: [notebook: string] }>()
const { t, locale } = useI18n()
const toast = useToast()
const dialog = ref<Dialog | null>(null)

function label(entry: NotesTrashEntry): string {
  if (entry.kind === 'notebook') return entry.notebook
  if (entry.kind === 'folder') return (entry.content as NoteFolder).name
  return (entry.content as Note).title || t('notes.untitled')
}

/** Where it was: a notebook was a tab; a folder in its notebook; a note there or in its folder. */
function origin(entry: NotesTrashEntry): string {
  if (entry.kind === 'notebook') return t('notesTrash.kind.notebook')
  return entry.folder === null ? entry.notebook : `${entry.notebook} / ${entry.folder}`
}

/** A notebook whose name is taken by now comes back as "<name> (restored)", numbered if need be. */
function freeName(name: string): string | undefined {
  if (!props.notebooks.includes(name)) return undefined
  for (let count = 1; ; count++) {
    const candidate = t('notesTrash.restoredName', { name, count }, count)
    if (!props.notebooks.includes(candidate)) return candidate
  }
}

async function restore(entry: NotesTrashEntry): Promise<void> {
  try {
    const { notebook } = await api.restoreNotes(
      entry.id,
      entry.kind === 'notebook' ? freeName(entry.notebook) : undefined,
    )
    emit('restored', notebook)
  } catch (error) {
    toast.error(error)
  }
}

async function confirmDialog(): Promise<void> {
  const current = dialog.value
  dialog.value = null
  try {
    if (current?.kind === 'delete') await api.deleteFromNotesTrash(current.entry.id)
    if (current?.kind === 'empty') await api.emptyNotesTrash()
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center gap-2">
      <h2 class="flex flex-1 items-center gap-2 font-semibold"><AppIcon name="trash" />{{ $t('notesTrash.title') }}</h2>
      <button v-if="entries.length > 0" class="btn-danger btn-small" @click="dialog = { kind: 'empty' }">
        {{ $t('trash.emptyAll') }}
      </button>
    </div>
    <p v-if="entries.length === 0" class="py-2 text-sm text-dim">{{ $t('trash.empty') }}</p>
    <ul v-else class="flex flex-col gap-2">
      <li v-for="entry in entries" :key="entry.id" class="card flex flex-wrap items-center gap-2 px-3 py-2">
        <AppIcon :name="entry.kind === 'notebook' ? 'notes' : entry.kind === 'folder' ? 'folder' : 'file'" class="shrink-0 text-muted" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium">{{ label(entry) }}</p>
          <p class="truncate text-xs text-muted">
            {{ origin(entry) }} · {{ $t('trash.deletedAt', { date: formatDate(new Date(entry.deleted_at), locale) }) }}
          </p>
        </div>
        <div class="flex gap-1.5">
          <button class="btn-secondary btn-small" @click="restore(entry)">
            <AppIcon name="resume" />{{ $t('trash.restore') }}
          </button>
          <button class="btn-danger btn-small" @click="dialog = { kind: 'delete', entry }">
            {{ $t('trash.deleteForever') }}
          </button>
        </div>
      </li>
    </ul>
    <ConfirmDialog
      v-if="dialog"
      :title="dialog.kind === 'empty' ? $t('trash.emptyAll') : $t('trash.deleteForever')"
      :message="
        dialog.kind === 'empty'
          ? $t('trash.confirmEmpty', { count: entries.length })
          : $t('trash.confirmDelete', { name: label(dialog.entry) })
      "
      :confirm-label="dialog.kind === 'empty' ? $t('trash.emptyAll') : $t('trash.deleteForever')"
      danger
      @confirm="confirmDialog"
      @close="dialog = null"
    />
  </div>
</template>
