<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type Conversation, type ConversationHit, type ModelChoice, type Reasoning } from '../api'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName, formatDate, formatSize } from '../format'
import type { WorkspaceTarget } from '../composables/useWorkspaceTab'
import BaseDialog from './BaseDialog.vue'
import ReasoningControl from './ReasoningControl.vue'
import ToggleSwitch from './ToggleSwitch.vue'

// defaultTarget: where the agent opens once started (null: the agent list).
const props = defineProps<{ path: string; defaultTarget: WorkspaceTarget | null }>()
const emit = defineEmits<{ started: [id: string, target: WorkspaceTarget | null]; close: [] }>()

const { profiles, loadProfiles, refresh } = useSessions()
const toast = useToast()
const selected = ref('')
const NO_REASONING: Reasoning = { effort: null, ultracode: false }
const reasoning = ref<Reasoning>(NO_REASONING)
const busy = ref(false)
// A worktree of its own: a second working copy on a new branch, next to the project.
const inWorktree = ref(false)
const branch = ref(defaultBranch())

function defaultBranch(): string {
  const now = new Date()
  const part = (value: number) => String(value).padStart(2, '0')
  return `agent-${now.getFullYear()}${part(now.getMonth() + 1)}${part(now.getDate())}-${part(now.getHours())}${part(now.getMinutes())}`
}
// The workspace to open the agent in: 'list' (none), 'unnamed' (this tab's), or 'named:<name>'.
const LIST_TARGET = 'list'
const UNNAMED_TARGET = 'unnamed'
const NAMED_PREFIX = 'named:'
function targetKey(target: WorkspaceTarget | null): string {
  if (target === null) return LIST_TARGET
  return target.name === null ? UNNAMED_TARGET : NAMED_PREFIX + target.name
}
function targetOf(key: string): WorkspaceTarget | null {
  if (key === LIST_TARGET) return null
  return { name: key === UNNAMED_TARGET ? null : key.slice(NAMED_PREFIX.length) }
}
const workspaceTarget = ref(targetKey(props.defaultTarget))
const workspaceNames = ref<string[]>([])
const conversations = ref<Conversation[]>([])
// Searching the earlier conversations' messages; shorter queries just show the list.
const MIN_QUERY_CHARS = 2
const SEARCH_DELAY_MS = 300
const query = ref('')
const hits = ref<ConversationHit[] | null>(null)
let searchTimer: number | undefined

watch(query, (current) => {
  window.clearTimeout(searchTimer)
  if (current.trim().length < MIN_QUERY_CHARS) {
    hits.value = null
    return
  }
  searchTimer = window.setTimeout(async () => {
    try {
      hits.value = await api.searchConversations(selected.value, props.path, current.trim())
    } catch (error) {
      toast.error(error)
    }
  }, SEARCH_DELAY_MS)
})

/** The excerpt in three parts, so the found words can be marked. */
function marked(excerpt: string): [string, string, string] {
  const words = query.value.trim()
  const at = excerpt.toLocaleLowerCase().indexOf(words.toLocaleLowerCase())
  if (at < 0) return [excerpt, '', '']
  return [excerpt.slice(0, at), excerpt.slice(at, at + words.length), excerpt.slice(at + words.length)]
}
const MILLISECONDS_PER_SECOND = 1000
const { locale } = useI18n()

const profile = computed(() => profiles.value.find((candidate) => candidate.name === selected.value))
// Profiles with a choice of models (e.g. the local ones): the list, the choice, its levels.
const models = ref<ModelChoice[]>([])
const model = ref<string | null>(null)
const modelLevels = ref<string[]>([])
const LAST_MODEL_KEY = 'agent-orc-last-model:'
const effortLevels = computed(() =>
  profile.value?.models ? modelLevels.value : (profile.value?.effort_levels ?? []),
)
// The folder's stored reasoning, preselected where the agent (or its model) takes it.
const folderReasoning = ref<Reasoning>(NO_REASONING)

/**
 * The folder's level where the model takes it; otherwise the next higher one it takes (as
 * lclaude translates), or its highest. The order is the profile's list of levels.
 */
function preselectReasoning(): void {
  const levels = effortLevels.value
  const stored = folderReasoning.value
  const order = profile.value?.effort_levels ?? []
  const wanted = order.indexOf(stored.effort ?? '')
  const effort =
    levels.length === 0
      ? null
      : levels.includes(stored.effort ?? '')
        ? stored.effort
        : (levels.find((level) => order.indexOf(level) >= wanted) ?? levels[levels.length - 1])
  reasoning.value = { effort, ultracode: stored.ultracode }
}

// For the chosen agent: preselect the folder's stored reasoning, list earlier conversations,
// and offer its models.
watch(selected, async (name) => {
  reasoning.value = NO_REASONING
  conversations.value = []
  models.value = []
  model.value = null
  if (!name) return
  try {
    folderReasoning.value = await api.folderReasoning(name, props.path)
    conversations.value = await api.conversations(name, props.path)
    if (profile.value?.models) {
      models.value = await api.agentModels(name)
      const last = localStorage.getItem(LAST_MODEL_KEY + name)
      const names = models.value.map((choice) => choice.name)
      model.value = last !== null && names.includes(last) ? last : (names[0] ?? null)
    } else {
      preselectReasoning()
    }
  } catch (error) {
    toast.error(error)
  }
})

watch(model, async (chosen) => {
  if (chosen === null || !profile.value?.models) return
  localStorage.setItem(LAST_MODEL_KEY + selected.value, chosen)
  try {
    modelLevels.value = await api.agentLevels(selected.value, chosen)
    preselectReasoning()
  } catch (error) {
    toast.error(error)
  }
})

onMounted(async () => {
  api.workspaces().then((named) => (workspaceNames.value = Object.keys(named).sort()), toast.error)
  if (profiles.value.length === 0) await loadProfiles()
  selected.value = profiles.value[0]?.name ?? ''
})

async function start(resume: boolean, conversation: string | null = null): Promise<void> {
  busy.value = true
  try {
    const session = await api.startSession(
      selected.value,
      props.path,
      resume,
      reasoning.value,
      conversation,
      inWorktree.value ? branch.value.trim() : null,
      model.value,
    )
    await refresh()
    emit('started', session.id, targetOf(workspaceTarget.value))
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <BaseDialog :title="$t('agent.title', { name: baseName(path) })" @close="emit('close')">
    <fieldset class="mb-5 flex flex-col gap-2">
      <legend class="mb-2 text-sm text-slate-400">{{ $t('agent.profile') }}</legend>
      <label
        v-for="profile in profiles"
        :key="profile.name"
        class="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border px-3"
        :class="selected === profile.name ? 'border-red-500 bg-red-900/20' : 'border-slate-600'"
      >
        <input v-model="selected" type="radio" :value="profile.name" class="accent-red-500" />
        {{ profile.label }}
      </label>
    </fieldset>
    <p v-if="profile?.hint" class="mb-4 rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-sm text-amber-200">
      {{ profile.hint }}
    </p>
    <label v-if="profile?.models" class="mb-5 flex flex-col gap-1 text-sm text-slate-400">
      {{ $t('agent.model') }}
      <select v-model="model" class="input text-sm text-slate-200">
        <option v-for="choice in models" :key="choice.name" :value="choice.name">
          {{ choice.note ? `${choice.name} – ${choice.note}` : choice.name }}
        </option>
      </select>
    </label>
    <ReasoningControl
      v-if="effortLevels.length"
      v-model="reasoning"
      :levels="effortLevels"
      :ultracode-offered="profile?.ultracode ?? false"
      class="mb-5"
    />
    <label class="mb-5 flex flex-col gap-1 text-sm text-slate-400">
      {{ $t('agent.workspace') }}
      <select v-model="workspaceTarget" class="input text-sm text-slate-200">
        <option :value="LIST_TARGET">{{ $t('agent.workspaceNone') }}</option>
        <option :value="UNNAMED_TARGET">{{ $t('workspace.unnamed') }}</option>
        <option v-for="name in workspaceNames" :key="name" :value="NAMED_PREFIX + name">{{ name }}</option>
      </select>
    </label>
    <div class="mb-5 flex flex-col gap-2">
      <ToggleSwitch class="h-7 self-start text-sm text-slate-300" :checked="inWorktree" @click="inWorktree = !inWorktree">
        {{ $t('agent.inWorktree') }}
      </ToggleSwitch>
      <template v-if="inWorktree">
        <input v-model="branch" class="input font-mono text-sm" :aria-label="$t('agent.branch')" :placeholder="$t('agent.branch')" />
        <p class="text-xs text-slate-500">{{ $t('agent.worktreeHint', { name: `${baseName(path)}.worktrees/${branch}` }) }}</p>
      </template>
    </div>
    <div class="flex flex-col gap-2">
      <button class="btn-primary" :disabled="busy || !selected || (profile?.models && !model)" @click="start(false)">
        {{ $t('agent.startNew') }}
      </button>
      <button class="btn-secondary" :disabled="busy || !selected || (profile?.models && !model)" @click="start(true)">
        {{ $t('agent.resume') }}
      </button>
      <button class="btn" @click="emit('close')">{{ $t('common.cancel') }}</button>
    </div>
    <div v-if="conversations.length" class="mt-5 border-t border-slate-700 pt-4">
      <h3 class="mb-2 text-sm text-slate-400">{{ $t('agent.earlier') }}</h3>
      <input
        v-model="query"
        type="search"
        class="input mb-2 w-full text-sm"
        :placeholder="$t('agent.searchConversations')"
        :aria-label="$t('agent.searchConversations')"
      />
      <ul v-if="hits" class="flex max-h-64 flex-col gap-1 overflow-y-auto">
        <li v-if="hits.length === 0" class="px-3 py-2 text-sm text-slate-500">{{ $t('agent.noHits') }}</li>
        <li v-for="hit in hits" :key="hit.id">
          <button
            class="flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left hover:bg-slate-700"
            :disabled="busy"
            @click="start(true, hit.id)"
          >
            <span class="w-full truncate text-sm text-slate-100">{{ hit.title || $t('agent.untitled') }}</span>
            <span class="line-clamp-2 text-xs text-slate-400">
              {{ marked(hit.excerpt)[0] }}<mark class="rounded bg-amber-400/30 px-0.5 text-amber-200">{{ marked(hit.excerpt)[1] }}</mark>{{ marked(hit.excerpt)[2] }}
            </span>
            <span class="text-xs text-slate-500">
              {{ formatDate(new Date(hit.modified * MILLISECONDS_PER_SECOND), locale) }}
              · {{ $t('agent.hitCount', { count: hit.matches }) }}
            </span>
          </button>
        </li>
      </ul>
      <ul v-else class="flex max-h-64 flex-col gap-1 overflow-y-auto">
        <li v-for="conversation in conversations" :key="conversation.id">
          <button
            class="flex w-full flex-col items-start rounded-lg px-3 py-2 text-left hover:bg-slate-700"
            :disabled="busy"
            @click="start(true, conversation.id)"
          >
            <span class="w-full truncate text-sm text-slate-100">
              {{ conversation.title || $t('agent.untitled') }}
            </span>
            <span class="text-xs text-slate-500">
              {{ formatDate(new Date(conversation.modified * MILLISECONDS_PER_SECOND), locale) }}
              · {{ formatSize(conversation.size) }}
              <span v-if="conversation.recently_active" class="text-amber-400">
                · {{ $t('agent.recentlyActive') }}
              </span>
            </span>
          </button>
        </li>
      </ul>
    </div>
  </BaseDialog>
</template>
