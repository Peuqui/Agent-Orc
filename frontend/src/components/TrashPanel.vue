<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type TrashEntry } from '../api'
import { PHONE_WIDTH } from '../device'
import { draggedPaths } from '../dragTypes'
import { useToast } from '../composables/useToast'
import { baseName, formatDate } from '../format'
import AppIcon from './AppIcon.vue'
import ConfirmDialog from './ConfirmDialog.vue'

// The user's trash (what was deleted through Agent-Orc, the desktop's trash too): restore, delete
// for good, empty. Files dragged here from the list are trashed (`trash`, for the list to do and
// reload); a restored one goes back to where it was (`restored`).
type Dialog = { kind: 'delete'; entry: TrashEntry } | { kind: 'empty' }

const emit = defineEmits<{ trash: [paths: string[]]; restored: [] }>()
const { locale } = useI18n()
const toast = useToast()
const entries = ref<TrashEntry[]>([])
const dialog = ref<Dialog | null>(null)
const dragOver = ref(false)
// On a phone the panel is folded away below the list until it is needed.
const open = ref(!PHONE_WIDTH.matches)

async function load(): Promise<void> {
  try {
    entries.value = await api.listTrash()
  } catch (error) {
    toast.error(error)
  }
}

async function run(action: () => Promise<unknown>): Promise<void> {
  dialog.value = null
  try {
    await action()
  } catch (error) {
    toast.error(error)
  }
  await load()
}

async function restore(entry: TrashEntry): Promise<void> {
  await run(() => api.restore(entry.id))
  emit('restored')
}

function confirmDialog(): void {
  const current = dialog.value
  if (current?.kind === 'delete') void run(() => api.deleteFromTrash(current.entry.id))
  if (current?.kind === 'empty') void run(() => api.emptyTrash())
}

function onDrop(event: DragEvent): void {
  dragOver.value = false
  const paths = draggedPaths(event)
  if (paths.length > 0) emit('trash', paths)
}

defineExpose({ load })
onMounted(load)
</script>

<template>
  <details
    class="card"
    :class="dragOver ? 'ring-2 ring-red-400 ring-inset' : ''"
    :open="open"
    @toggle="open = ($event.target as HTMLDetailsElement).open"
    @dragover.prevent="dragOver = true"
    @dragleave="dragOver = false"
    @drop.prevent="onDrop"
  >
    <summary class="flex cursor-pointer items-center gap-2 px-4 py-3 font-semibold select-none">
      <AppIcon name="trash" />{{ $t('trash.title') }}
      <span class="text-sm font-normal text-slate-400">{{ entries.length }}</span>
    </summary>
    <div class="flex flex-col gap-3 border-t border-slate-700 p-3">
      <p class="text-xs text-slate-500">{{ $t('trash.dropHint') }}</p>
      <button v-if="entries.length > 0" class="btn-danger btn-small w-full" @click="dialog = { kind: 'empty' }">
        {{ $t('trash.emptyAll') }}
      </button>
      <p v-if="entries.length === 0" class="py-2 text-center text-sm text-slate-400">{{ $t('trash.empty') }}</p>
      <ul v-else class="flex flex-col gap-2">
        <li v-for="entry in entries" :key="entry.id" class="rounded-lg border border-slate-700 p-2">
          <div class="flex items-start gap-2">
            <AppIcon :name="entry.is_dir ? 'folder' : 'file'" class="mt-0.5 shrink-0 text-slate-500" />
            <div class="min-w-0">
              <p class="truncate text-sm font-medium">{{ baseName(entry.original_path) }}</p>
              <p class="truncate text-xs text-slate-500" :title="entry.original_path">{{ entry.original_path }}</p>
              <p class="text-xs text-slate-400">
                {{ $t('trash.deletedAt', { date: formatDate(new Date(entry.deleted_at), locale) }) }}
              </p>
            </div>
          </div>
          <div class="mt-2 flex flex-wrap gap-1.5">
            <button class="btn-secondary btn-small" @click="restore(entry)">
              <AppIcon name="resume" />{{ $t('trash.restore') }}
            </button>
            <button class="btn-danger btn-small" @click="dialog = { kind: 'delete', entry }">
              {{ $t('trash.deleteForever') }}
            </button>
          </div>
        </li>
      </ul>
    </div>
    <ConfirmDialog
      v-if="dialog"
      :title="dialog.kind === 'empty' ? $t('trash.emptyAll') : $t('trash.deleteForever')"
      :message="
        dialog.kind === 'empty'
          ? $t('trash.confirmEmpty', { count: entries.length })
          : $t('trash.confirmDelete', { name: baseName(dialog.entry.original_path) })
      "
      :confirm-label="dialog.kind === 'empty' ? $t('trash.emptyAll') : $t('trash.deleteForever')"
      danger
      @confirm="confirmDialog"
      @close="dialog = null"
    />
  </details>
</template>
