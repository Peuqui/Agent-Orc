<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, type FileEntry } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BaseDialog from '../components/BaseDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import InputDialog from '../components/InputDialog.vue'
import StartAgentDialog from '../components/StartAgentDialog.vue'
import { loadTabState, openWorkspace, useOtherTabs, type WorkspaceTarget } from '../composables/useWorkspaceTab'
import { useScope } from '../composables/useScope'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName, formatCountdown, formatDate, formatSize, parentPath } from '../format'

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

async function run(action: () => Promise<unknown>): Promise<void> {
  dialog.value = null
  try {
    await action()
  } catch (error) {
    toast.error(error)
  }
  await loadEntries()
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

// Joins the tabs' channel, so a workspace open in another tab is found (and not opened twice).
useOtherTabs()

// From a workspace's "+": preselected is the workspace of this tab.
const defaultTarget = computed<WorkspaceTarget | null>(() =>
  forWorkspace.value ? { name: loadTabState().name } : null,
)

function onAgentStarted(id: string, target: WorkspaceTarget | null): void {
  dialog.value = null
  if (target === null) void router.push('/sessions')
  else openWorkspace(router, target.name, id)
}

onMounted(async () => {
  await loadScope()
  await loadEntries()
})
watch(currentPath, loadEntries)
</script>

<template>
  <section>
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
        @click="dialog = { kind: 'unlock' }"
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

    <div class="mb-4 grid grid-cols-2 gap-2">
      <button class="btn-secondary" @click="dialog = { kind: 'newFolder' }">
        <AppIcon name="plus" />{{ $t('files.newFolder') }}
      </button>
      <button class="btn-primary" @click="dialog = { kind: 'agent', path: currentPath }">
        <AppIcon name="play" />{{ $t('files.startAgent') }}
      </button>
    </div>

    <p v-if="entries.length === 0" class="card p-6 text-center text-slate-400">{{ $t('files.empty') }}</p>
    <ul v-else class="card divide-y divide-slate-700">
      <li v-for="entry in entries" :key="entry.path" class="flex items-center">
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

    <BaseDialog v-if="dialog?.kind === 'actions'" :title="dialog.entry.name" @close="dialog = null">
      <div class="flex flex-col gap-2">
        <button
          v-if="dialog.entry.is_dir"
          class="btn-primary"
          @click="dialog = { kind: 'agent', path: dialog.entry.path }"
        >
          <AppIcon name="play" />{{ $t('files.startAgent') }}
        </button>
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
      :default-target="defaultTarget"
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
