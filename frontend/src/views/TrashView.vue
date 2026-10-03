<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type TrashEntry } from '../api'
import AppIcon from '../components/AppIcon.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { useToast } from '../composables/useToast'
import { baseName, formatDate } from '../format'

type Dialog = { kind: 'delete'; entry: TrashEntry } | { kind: 'empty' }

const { locale } = useI18n()
const toast = useToast()
const entries = ref<TrashEntry[]>([])
const dialog = ref<Dialog | null>(null)

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

function restore(entry: TrashEntry): void {
  void run(() => api.restore(entry.id))
}

function confirmDialog(): void {
  const current = dialog.value
  if (current?.kind === 'delete') void run(() => api.deleteFromTrash(current.entry.id))
  if (current?.kind === 'empty') void run(() => api.emptyTrash())
}

onMounted(load)
</script>

<template>
  <section>
    <button
      v-if="entries.length > 0"
      class="btn-danger mb-4 w-full"
      @click="dialog = { kind: 'empty' }"
    >
      <AppIcon name="trash" />{{ $t('trash.emptyAll') }}
    </button>

    <p v-if="entries.length === 0" class="card p-6 text-center text-slate-400">{{ $t('trash.empty') }}</p>
    <ul v-else class="flex flex-col gap-3">
      <li v-for="entry in entries" :key="entry.id" class="card p-4">
        <div class="mb-3 flex items-start gap-3">
          <AppIcon :name="entry.is_dir ? 'folder' : 'file'" class="mt-0.5 text-slate-500" />
          <div class="min-w-0">
            <h2 class="truncate font-semibold">{{ baseName(entry.original_path) }}</h2>
            <p class="truncate text-xs text-slate-500">{{ entry.original_path }}</p>
            <p class="mt-1 text-xs text-slate-400">
              {{ $t('trash.deletedAt', { date: formatDate(new Date(entry.deleted_at), locale) }) }}
            </p>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="btn-secondary" @click="restore(entry)">
            <AppIcon name="resume" />{{ $t('trash.restore') }}
          </button>
          <button class="btn-danger" @click="dialog = { kind: 'delete', entry }">
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
          : $t('trash.confirmDelete', { name: baseName(dialog.entry.original_path) })
      "
      :confirm-label="dialog.kind === 'empty' ? $t('trash.emptyAll') : $t('trash.deleteForever')"
      danger
      @confirm="confirmDialog"
      @close="dialog = null"
    />
  </section>
</template>
