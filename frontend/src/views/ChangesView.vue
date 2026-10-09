<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, api, type FileChange } from '../api'
import AppIcon from '../components/AppIcon.vue'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'

// What an agent changed in its project: the changed files, each one's diff on a tap. Read only;
// the agent stages and commits itself.
const props = defineProps<{ id: string }>()
const HTTP_UNPROCESSABLE = 422

const router = useRouter()
const toast = useToast()
const { sessions } = useSessions()

const files = ref<FileChange[] | null>(null)
const notARepository = ref(false)
const open = ref<string | null>(null)
const diffs = ref(new Map<string, { text: string; truncated: boolean }>())

const folder = computed(() => {
  const session = sessions.value.find((candidate) => candidate.id === props.id)
  return session ? session.name : props.id
})

async function load(): Promise<void> {
  diffs.value = new Map()
  open.value = null
  try {
    files.value = await api.changes(props.id)
  } catch (error) {
    if (error instanceof ApiError && error.status === HTTP_UNPROCESSABLE) notARepository.value = true
    else toast.error(error)
  }
}

void load()

async function toggle(path: string): Promise<void> {
  if (open.value === path) {
    open.value = null
    return
  }
  open.value = path
  if (diffs.value.has(path)) return
  try {
    diffs.value.set(path, await api.changeDiff(props.id, path))
  } catch (error) {
    toast.error(error)
  }
}

/** Git's status as a word; the raw code for anything unusual. */
const STATUS_KEYS: Record<string, string> = { M: 'modified', A: 'added', D: 'deleted', R: 'renamed', '??': 'new' }

function lineClass(line: string): string {
  if (line.startsWith('+++') || line.startsWith('---')) return 'text-slate-500'
  if (line.startsWith('+')) return 'bg-green-950/60 text-green-300'
  if (line.startsWith('-')) return 'bg-red-950/60 text-red-300'
  if (line.startsWith('@@')) return 'text-cyan-400'
  if (line.startsWith('diff ') || line.startsWith('index ')) return 'text-slate-500'
  return 'text-slate-300'
}
</script>

<template>
  <div class="flex h-full flex-col bg-slate-900">
    <header class="flex items-center gap-1 border-b border-slate-800 px-1 py-1">
      <button class="btn-icon" :aria-label="$t('terminal.back')" @click="router.back()">
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <h1 class="min-w-0 flex-1 truncate font-semibold">{{ $t('changes.title', { name: folder }) }}</h1>
      <button class="btn-icon" :aria-label="$t('changes.refresh')" :title="$t('changes.refresh')" @click="load">
        <AppIcon name="resume" />
      </button>
    </header>

    <main class="min-h-0 flex-1 overflow-y-auto p-2">
      <p v-if="notARepository" class="p-6 text-center text-slate-400">{{ $t('changes.notARepository') }}</p>
      <p v-else-if="files?.length === 0" class="p-6 text-center text-slate-400">{{ $t('changes.none') }}</p>
      <ul v-else-if="files" class="flex flex-col gap-1">
        <li v-for="file in files" :key="file.path" class="card overflow-hidden">
          <button class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-700" @click="toggle(file.path)">
            <span
              class="w-20 shrink-0 rounded px-1.5 py-0.5 text-center text-xs"
              :class="{
                'bg-green-900/50 text-green-300': file.status === '??' || file.status === 'A',
                'bg-red-900/50 text-red-300': file.status === 'D',
                'bg-amber-900/50 text-amber-300': file.status === 'M' || file.status === 'R',
                'bg-slate-700 text-slate-300': !STATUS_KEYS[file.status],
              }"
            >
              {{ STATUS_KEYS[file.status] ? $t(`changes.status.${STATUS_KEYS[file.status]}`) : file.status }}
            </span>
            <span class="min-w-0 flex-1 truncate font-mono text-xs text-slate-200">{{ file.path }}</span>
            <AppIcon name="up" class="size-4 shrink-0 text-slate-500 transition-transform" :class="open === file.path ? '' : 'rotate-180'" />
          </button>
          <div v-if="open === file.path" class="overflow-x-auto border-t border-slate-700 bg-slate-950/60">
            <p v-if="!diffs.has(file.path)" class="p-3 text-xs text-slate-500">{{ $t('changes.loading') }}</p>
            <pre
              v-else
              class="py-2 font-mono text-xs leading-relaxed"
            ><span v-for="(line, index) in diffs.get(file.path)!.text.split('\n')" :key="index" class="block px-3 whitespace-pre" :class="lineClass(line)">{{ line || ' ' }}</span></pre>
            <p v-if="diffs.get(file.path)?.truncated" class="px-3 pb-2 text-xs text-amber-300">{{ $t('changes.truncated') }}</p>
          </div>
        </li>
      </ul>
    </main>
  </div>
</template>
