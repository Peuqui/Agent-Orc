<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, api, type ExistingPath, type FileChange } from '../api'
import { existingPaths } from '../existingPaths'
import AppIcon from '../components/AppIcon.vue'
import { openExistingPath } from '../composables/useFileLinks'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { useViewZoom } from '../composables/useViewZoom'

// What an agent changed in its project: the changed files, each one's diff on a tap. Read only;
// the agent stages and commits itself.
const props = defineProps<{ id: string }>()
const HTTP_UNPROCESSABLE = 422

const router = useRouter()
const toast = useToast()
// The views' font size scales the list of changes (see useViewZoom).
const scroller = ref<HTMLElement>()
const zoomed = ref<HTMLElement>()
const { zoomStyle } = useViewZoom(zoomed, scroller)
const { sessions } = useSessions()

const files = ref<FileChange[] | null>(null)
const notARepository = ref(false)
const open = ref<string | null>(null)
const diffs = ref(new Map<string, { text: string; truncated: boolean }>())

const session = computed(() => sessions.value.find((candidate) => candidate.id === props.id))
const folder = computed(() => (session.value ? session.value.name : props.id))

// Which of the changed paths exist (a deleted file does not), with their full paths: only those
// can be opened, as everywhere else (useFileLinks).
const existing = ref<Record<string, ExistingPath>>({})
watch(
  () => [files.value, session.value?.path] as const,
  async ([changed, base]) => {
    if (changed === null || base === undefined) return
    try {
      existing.value = await existingPaths(base, changed.map((file) => file.path))
    } catch (error) {
      toast.error(error)
    }
  },
)

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
  if (line.startsWith('+++') || line.startsWith('---')) return 'text-muted'
  if (line.startsWith('+')) return 'bg-ok-900/60 text-ok-300'
  if (line.startsWith('-')) return 'bg-accent-900/60 text-accent-300'
  if (line.startsWith('@@')) return 'text-hunk'
  if (line.startsWith('diff ') || line.startsWith('index ')) return 'text-muted'
  return 'text-soft'
}
</script>

<template>
  <div class="flex h-full flex-col bg-page">
    <header class="flex items-center gap-1 border-b border-line-subtle px-1 py-1">
      <button class="btn-icon" :aria-label="$t('terminal.back')" @click="router.back()">
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <h1 class="min-w-0 flex-1 truncate font-semibold">{{ $t('changes.title', { name: folder }) }}</h1>
      <button class="btn-icon" :aria-label="$t('changes.refresh')" :title="$t('changes.refresh')" @click="load">
        <AppIcon name="resume" />
      </button>
    </header>

    <main ref="scroller" class="min-h-0 flex-1 overflow-y-auto p-2">
      <p v-if="notARepository" class="p-6 text-center text-dim">{{ $t('changes.notARepository') }}</p>
      <p v-else-if="files?.length === 0" class="p-6 text-center text-dim">{{ $t('changes.none') }}</p>
      <ul v-else-if="files" ref="zoomed" class="flex flex-col gap-1" :style="zoomStyle">
        <li v-for="file in files" :key="file.path" class="card overflow-hidden">
          <div class="flex items-center hover:bg-raised">
          <button class="flex min-w-0 flex-1 items-center gap-2 py-2 pl-3 text-left text-sm" @click="toggle(file.path)">
            <span
              class="w-20 shrink-0 rounded px-1.5 py-0.5 text-center text-xs"
              :class="{
                'bg-ok-900/50 text-ok-300': file.status === '??' || file.status === 'A',
                'bg-accent-900/50 text-accent-300': file.status === 'D',
                'bg-highlight-900/50 text-highlight-300': file.status === 'M' || file.status === 'R',
                'bg-raised text-soft': !STATUS_KEYS[file.status],
              }"
            >
              {{ STATUS_KEYS[file.status] ? $t(`changes.status.${STATUS_KEYS[file.status]}`) : file.status }}
            </span>
            <span class="min-w-0 flex-1 truncate font-mono text-xs text-main">{{ file.path }}</span>
            <AppIcon name="up" class="size-4 shrink-0 text-muted transition-transform" :class="open === file.path ? '' : 'rotate-180'" />
          </button>
          <button
            v-if="existing[file.path]"
            class="btn-icon shrink-0"
            :title="$t(existing[file.path]!.kind === 'folder' ? 'changes.openFolder' : 'changes.openFile')"
            :aria-label="$t(existing[file.path]!.kind === 'folder' ? 'changes.openFolder' : 'changes.openFile')"
            @click="openExistingPath(router, existing[file.path]!, null)"
          >
            <AppIcon name="external" />
          </button>
          </div>
          <div v-if="open === file.path" class="overflow-x-auto border-t border-line bg-sunken/60">
            <p v-if="!diffs.has(file.path)" class="p-3 text-xs text-muted">{{ $t('changes.loading') }}</p>
            <pre
              v-else
              class="py-2 font-mono text-xs leading-relaxed"
            ><span v-for="(line, index) in diffs.get(file.path)!.text.split('\n')" :key="index" class="block px-3 whitespace-pre" :class="lineClass(line)">{{ line || ' ' }}</span></pre>
            <p v-if="diffs.get(file.path)?.truncated" class="px-3 pb-2 text-xs text-highlight-300">{{ $t('changes.truncated') }}</p>
          </div>
        </li>
      </ul>
    </main>
  </div>
</template>
