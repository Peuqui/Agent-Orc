<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type CleanupConversation, type ProjectConversations } from '../api'
import { PHONE_WIDTH } from '../device'
import { useScope } from '../composables/useScope'
import { useToast } from '../composables/useToast'
import { baseName, formatDate, formatSize } from '../format'
import AppIcon from './AppIcon.vue'
import ConfirmDialog from './ConfirmDialog.vue'

// Earlier conversations of every project in reach, to delete for good (not into the trash): the
// scope is the file list's, so the safety switch widens it to the home directory too.
const SECONDS_PER_DAY = 86400
// What Claude Code deletes on its own after (cleanupPeriodDays in its settings).
const DEFAULT_OLDER_THAN_DAYS = 7

const { locale, t } = useI18n()
const toast = useToast()
const { secondsLeft } = useScope()
const projects = ref<ProjectConversations[]>([])
// "<directory>/<id>" of the ticked conversations.
const selected = ref(new Set<string>())
const olderThanDays = ref(DEFAULT_OLDER_THAN_DAYS)
const confirming = ref(false)
// On a phone the panel is folded away until it is needed.
const open = ref(!PHONE_WIDTH.matches)

const keyOf = (project: ProjectConversations, conversation: CleanupConversation): string =>
  `${project.directory}/${conversation.id}`
const everyConversation = computed(() =>
  projects.value.flatMap((project) =>
    project.conversations.map((conversation) => ({ project, conversation, key: keyOf(project, conversation) })),
  ),
)
const chosen = computed(() => everyConversation.value.filter(({ key }) => selected.value.has(key)))
const chosenBytes = computed(() => chosen.value.reduce((sum, { conversation }) => sum + conversation.size, 0))
const totalBytes = computed(() => everyConversation.value.reduce((sum, { conversation }) => sum + conversation.size, 0))

async function load(): Promise<void> {
  try {
    projects.value = await api.listAllConversations()
  } catch (error) {
    toast.error(error)
  }
  // Only what still exists stays ticked.
  const present = new Set(everyConversation.value.map(({ key }) => key))
  selected.value = new Set([...selected.value].filter((key) => present.has(key)))
}

function toggle(key: string): void {
  const next = new Set(selected.value)
  if (!next.delete(key)) next.add(key)
  selected.value = next
}

function setProject(project: ProjectConversations, on: boolean): void {
  const next = new Set(selected.value)
  for (const conversation of project.conversations) {
    if (conversation.in_use) continue
    if (on) next.add(keyOf(project, conversation))
    else next.delete(keyOf(project, conversation))
  }
  selected.value = next
}

function projectFullyChosen(project: ProjectConversations): boolean {
  const free = project.conversations.filter((conversation) => !conversation.in_use)
  return free.length > 0 && free.every((conversation) => selected.value.has(keyOf(project, conversation)))
}

function chooseOlderThan(): void {
  const limit = Date.now() / 1000 - olderThanDays.value * SECONDS_PER_DAY
  selected.value = new Set(
    everyConversation.value
      .filter(({ conversation }) => !conversation.in_use && conversation.modified < limit)
      .map(({ key }) => key),
  )
}

async function deleteChosen(): Promise<void> {
  confirming.value = false
  try {
    const result = await api.deleteConversations(
      chosen.value.map(({ project, conversation }) => ({ directory: project.directory, id: conversation.id })),
    )
    toast.info(t('cleanup.done', { count: result.deleted, size: formatSize(result.freed_bytes) }))
  } catch (error) {
    toast.error(error)
  }
  await load()
}

// The scope widens or narrows with the safety switch: another list.
watch(
  () => secondsLeft.value > 0,
  () => void load(),
)
onMounted(load)
</script>

<template>
  <details class="card mt-4" :open="open" @toggle="open = ($event.target as HTMLDetailsElement).open">
    <summary class="flex cursor-pointer items-center gap-2 px-4 py-3 font-semibold select-none">
      <AppIcon name="answers" />{{ $t('cleanup.title') }}
      <span class="text-sm font-normal text-slate-400">{{ everyConversation.length }} · {{ formatSize(totalBytes) }}</span>
    </summary>
    <div class="flex flex-col gap-3 border-t border-slate-700 p-3">
      <p class="text-xs text-slate-500">{{ $t('cleanup.hint') }}</p>
      <p v-if="everyConversation.length === 0" class="py-2 text-center text-sm text-slate-400">{{ $t('cleanup.empty') }}</p>
      <template v-else>
        <div class="flex flex-wrap items-center gap-2 text-sm">
          <label class="flex items-center gap-1.5 text-slate-300">
            {{ $t('cleanup.olderThan') }}
            <input v-model.number="olderThanDays" type="number" min="0" class="input w-20 text-sm" />
            {{ $t('cleanup.days') }}
          </label>
          <button class="btn-secondary btn-small" @click="chooseOlderThan">{{ $t('cleanup.choose') }}</button>
        </div>
        <button class="btn-danger btn-small w-full" :disabled="chosen.length === 0" @click="confirming = true">
          {{ $t('cleanup.deleteChosen', { count: chosen.length, size: formatSize(chosenBytes) }) }}
        </button>
        <section v-for="project in projects" :key="project.directory" class="rounded-lg border border-slate-700">
          <label class="flex items-start gap-2 border-b border-slate-700 p-2">
            <input
              type="checkbox"
              class="mt-1"
              :checked="projectFullyChosen(project)"
              @change="setProject(project, ($event.target as HTMLInputElement).checked)"
            />
            <span class="min-w-0">
              <span class="block truncate text-sm font-medium">{{ baseName(project.folder) }}</span>
              <span class="block truncate text-xs text-slate-500" :title="project.folder">{{ project.folder }}</span>
            </span>
          </label>
          <ul>
            <li v-for="conversation in project.conversations" :key="conversation.id">
              <label class="flex items-start gap-2 px-2 py-1.5" :class="conversation.in_use ? 'opacity-50' : ''">
                <input
                  type="checkbox"
                  class="mt-1"
                  :checked="selected.has(keyOf(project, conversation))"
                  :disabled="conversation.in_use"
                  @change="toggle(keyOf(project, conversation))"
                />
                <span class="min-w-0">
                  <span class="block truncate text-sm">{{ conversation.title || conversation.id }}</span>
                  <span class="block text-xs text-slate-400">
                    {{ formatDate(new Date(conversation.modified * 1000), locale) }} · {{ formatSize(conversation.size) }}
                    <span v-if="conversation.in_use" class="text-amber-300"> · {{ $t('cleanup.inUse') }}</span>
                  </span>
                </span>
              </label>
            </li>
          </ul>
        </section>
      </template>
    </div>
    <ConfirmDialog
      v-if="confirming"
      :title="$t('cleanup.deleteTitle')"
      :message="$t('cleanup.confirm', { count: chosen.length, size: formatSize(chosenBytes) })"
      :confirm-label="$t('trash.deleteForever')"
      danger
      @confirm="deleteChosen"
      @close="confirming = false"
    />
  </details>
</template>
