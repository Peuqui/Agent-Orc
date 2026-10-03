<script setup lang="ts">
import { indentWithTab } from '@codemirror/commands'
import { LanguageDescription } from '@codemirror/language'
import { languages } from '@codemirror/language-data'
import { openSearchPanel } from '@codemirror/search'
import { Compartment, EditorState } from '@codemirror/state'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView, keymap } from '@codemirror/view'
import { basicSetup } from 'codemirror'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, api } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BaseDialog from '../components/BaseDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { useToast } from '../composables/useToast'
import { baseName, parentPath } from '../format'

const props = defineProps<{ path: string }>()

const FONT_SIZE_KEY = 'ai-orc-editor-font-size'
const DEFAULT_FONT_SIZE = 14
const MIN_FONT_SIZE = 8
const MAX_FONT_SIZE = 28
const HTTP_CONFLICT = 409

const router = useRouter()
const toast = useToast()

const container = ref<HTMLElement>()
const loaded = ref(false)
const dirty = ref(false)
const saving = ref(false)
const dialog = ref<'conflict' | 'leave' | null>(null)
const fontSize = ref(Number(localStorage.getItem(FONT_SIZE_KEY)) || DEFAULT_FONT_SIZE)
let version = ''
let view: EditorView | null = null

const language = new Compartment()
const fontTheme = new Compartment()
const name = computed(() => baseName(props.path))

function fontSizeTheme(size: number) {
  return EditorView.theme({ '&': { fontSize: `${size}px` }, '.cm-scroller': { fontFamily: 'ui-monospace, monospace' } })
}

function createView(content: string): void {
  view = new EditorView({
    parent: container.value,
    state: EditorState.create({
      doc: content,
      extensions: [
        basicSetup,
        keymap.of([indentWithTab]),
        oneDark,
        EditorView.lineWrapping,
        language.of([]),
        fontTheme.of(fontSizeTheme(fontSize.value)),
        EditorView.theme({ '&': { height: '100%' } }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) dirty.value = true
        }),
      ],
    }),
  })
}

async function loadLanguage(): Promise<void> {
  const description = LanguageDescription.matchFilename(languages, name.value)
  if (!description || !view) return
  view.dispatch({ effects: language.reconfigure(await description.load()) })
}

async function load(): Promise<void> {
  const file = await api.readFile(props.path)
  version = file.version
  if (view) {
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: file.content } })
  } else {
    createView(file.content)
    void loadLanguage()
  }
  dirty.value = false
  loaded.value = true
}

async function save(expected: string): Promise<void> {
  if (!view) return
  saving.value = true
  try {
    const result = await api.writeFile(props.path, view.state.doc.toString(), expected)
    version = result.version
    dirty.value = false
  } catch (error) {
    if (error instanceof ApiError && error.status === HTTP_CONFLICT) dialog.value = 'conflict'
    else toast.error(error)
  } finally {
    saving.value = false
  }
}

async function overwrite(): Promise<void> {
  dialog.value = null
  // Take the newer file's version as the expected one: an explicit, informed overwrite.
  const current = await api.readFile(props.path)
  await save(current.version)
}

async function reload(): Promise<void> {
  dialog.value = null
  await load()
}

function changeFontSize(delta: number): void {
  fontSize.value = Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, fontSize.value + delta))
  localStorage.setItem(FONT_SIZE_KEY, String(fontSize.value))
  view?.dispatch({ effects: fontTheme.reconfigure(fontSizeTheme(fontSize.value)) })
}

function leave(): void {
  dialog.value = null
  void router.push({ path: '/files', query: { path: parentPath(props.path) } })
}

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    toast.error(error)
    leave()
  }
})

onBeforeUnmount(() => view?.destroy())
</script>

<template>
  <div class="flex h-dvh flex-col bg-slate-900">
    <header class="flex items-center gap-1 border-b border-slate-800 px-1 py-1">
      <button
        class="btn-icon"
        :aria-label="$t('terminal.back')"
        @click="dirty ? (dialog = 'leave') : leave()"
      >
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <h1 class="min-w-0 flex-1 truncate font-semibold">
        {{ name }}<span v-if="dirty" class="text-red-400"> ●</span>
      </h1>
      <button class="btn-icon" :aria-label="$t('editor.search')" @click="view && openSearchPanel(view)">
        <AppIcon name="search" />
      </button>
      <button class="btn-icon text-sm" :aria-label="$t('terminal.smaller')" @click="changeFontSize(-1)">A−</button>
      <button class="btn-icon text-base" :aria-label="$t('terminal.larger')" @click="changeFontSize(1)">A+</button>
      <button class="btn-primary min-h-10 px-3" :disabled="!dirty || saving" @click="save(version)">
        {{ $t('common.save') }}
      </button>
    </header>

    <div ref="container" class="min-h-0 flex-1 overflow-hidden" />

    <BaseDialog v-if="dialog === 'conflict'" :title="$t('editor.conflictTitle')" @close="dialog = null">
      <p class="mb-5 text-slate-300">{{ $t('errors.FileConflictError') }}</p>
      <div class="flex flex-col gap-2">
        <button class="btn-secondary" @click="reload">{{ $t('editor.reload') }}</button>
        <button class="btn-danger" @click="overwrite">{{ $t('editor.overwrite') }}</button>
        <button class="btn" @click="dialog = null">{{ $t('common.cancel') }}</button>
      </div>
    </BaseDialog>
    <ConfirmDialog
      v-if="dialog === 'leave'"
      :title="$t('editor.unsavedTitle')"
      :message="$t('editor.unsavedMessage')"
      :confirm-label="$t('editor.discard')"
      danger
      @confirm="leave"
      @close="dialog = null"
    />
  </div>
</template>
