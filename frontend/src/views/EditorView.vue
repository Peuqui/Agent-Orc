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
import { ApiError, api, rawFileUrl } from '../api'
import AppIcon from '../components/AppIcon.vue'
import BaseDialog from '../components/BaseDialog.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { useToast } from '../composables/useToast'
import { baseName, parentPath } from '../format'
import { isExternal, linkedPath, renderMarkdown } from '../markdown'

// line: where to start, e.g. from "main.py:42" in an agent's output.
const props = defineProps<{ path: string; line: number | null }>()

// What the file is shown as: text in the editor, Markdown also as a page, a picture, a sound or
// a video the browser plays, or (not text, too large) only offered to download.
type Kind = 'text' | 'markdown' | 'image' | 'audio' | 'video' | 'binary'
const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif']
const AUDIO_EXTENSIONS = ['wav', 'mp3', 'ogg', 'oga', 'opus', 'flac', 'm4a', 'aac']
const VIDEO_EXTENSIONS = ['mp4', 'webm', 'ogv', 'mov']
const MARKDOWN_EXTENSIONS = ['md', 'markdown']
const NOT_SHOWN_AS_TEXT = ['NotTextError', 'FileTooLargeError']

const FONT_SIZE_KEY = 'agent-orc-editor-font-size'
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
const extension = computed(() => name.value.split('.').pop()?.toLowerCase() ?? '')
function kindOfExtension(extensionName: string): Kind {
  if (IMAGE_EXTENSIONS.includes(extensionName)) return 'image'
  if (AUDIO_EXTENSIONS.includes(extensionName)) return 'audio'
  if (VIDEO_EXTENSIONS.includes(extensionName)) return 'video'
  return 'text'
}
const kind = ref<Kind>(kindOfExtension(extension.value))
// Markdown opens as a page; the editor keeps the text for switching back.
const previewing = ref(MARKDOWN_EXTENSIONS.includes(extension.value))
const previewHtml = ref('')
const editable = computed(() => kind.value === 'text' || kind.value === 'markdown')

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

function showPreview(): void {
  previewHtml.value = renderMarkdown(view?.state.doc.toString() ?? '', props.path)
  previewing.value = true
}

function togglePreview(): void {
  if (previewing.value) previewing.value = false
  else showPreview()
}

/** Links in the page: other files of the project open here, anything else in a new tab. */
function followLink(event: MouseEvent): void {
  const link = (event.target as Element).closest('a')
  const href = link?.getAttribute('href')
  if (!href || href.startsWith('#')) return
  event.preventDefault()
  if (isExternal(href)) window.open(href, '_blank', 'noopener')
  else void router.push({ path: '/edit', query: { path: linkedPath(props.path, href) } })
}

function goToLine(line: number): void {
  if (!view) return
  const target = view.state.doc.line(Math.min(line, view.state.doc.lines))
  view.dispatch({ selection: { anchor: target.from }, scrollIntoView: true })
}

async function load(): Promise<void> {
  if (kind.value === 'image' || kind.value === 'audio' || kind.value === 'video') {
    loaded.value = true
    return
  }
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
  if (MARKDOWN_EXTENSIONS.includes(extension.value)) {
    kind.value = 'markdown'
    // Asked for a line: the text there, not the page.
    if (props.line === null && previewing.value) showPreview()
    else previewing.value = false
  }
  if (props.line !== null) goToLine(props.line)
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
  // Back to where it was opened from (a terminal, the changes); otherwise to its folder.
  if (window.history.state?.back) router.back()
  else void router.push({ path: '/files', query: { path: parentPath(props.path) } })
}

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    if (error instanceof ApiError && NOT_SHOWN_AS_TEXT.includes(error.code)) {
      kind.value = 'binary'
      loaded.value = true
      return
    }
    toast.error(error)
    leave()
  }
})

onBeforeUnmount(() => view?.destroy())
</script>

<template>
  <div class="flex h-full flex-col bg-slate-900">
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
      <button
        v-if="kind === 'markdown'"
        class="btn-secondary btn-small"
        :title="$t(previewing ? 'editor.edit' : 'editor.preview')"
        :aria-label="$t(previewing ? 'editor.edit' : 'editor.preview')"
        @click="togglePreview"
      >
        <!-- On phones the icon only, so the file's name keeps its room. -->
        <AppIcon :name="previewing ? 'pencil' : 'eye'" /><span class="max-sm:hidden">{{
          $t(previewing ? 'editor.edit' : 'editor.preview')
        }}</span>
      </button>
      <template v-if="editable && !previewing">
        <button class="btn-icon" :aria-label="$t('editor.search')" @click="view && openSearchPanel(view)">
          <AppIcon name="search" />
        </button>
        <button class="btn-icon text-sm" :aria-label="$t('terminal.smaller')" @click="changeFontSize(-1)">A−</button>
        <button class="btn-icon text-base" :aria-label="$t('terminal.larger')" @click="changeFontSize(1)">A+</button>
      </template>
      <a
        class="btn-icon"
        :href="rawFileUrl(path, true)"
        :title="$t('editor.download')"
        :aria-label="$t('editor.download')"
      >
        <AppIcon name="download" />
      </a>
      <!-- Also when changes wait while the page is shown, so they are not hidden. -->
      <button
        v-if="editable && (!previewing || dirty)"
        class="btn-primary min-h-10 px-3"
        :disabled="!dirty || saving"
        @click="save(version)"
      >
        {{ $t('common.save') }}
      </button>
    </header>

    <div v-show="editable && !previewing" ref="container" class="min-h-0 flex-1 overflow-hidden" />
    <!-- v-html is safe here: renderMarkdown passes the HTML through DOMPurify. -->
    <article
      v-if="kind === 'markdown' && previewing"
      class="markdown min-h-0 flex-1 overflow-y-auto px-4 py-3 sm:px-8"
      @click="followLink"
      v-html="previewHtml"
    />
    <div v-if="kind === 'image'" class="flex min-h-0 flex-1 items-center justify-center overflow-auto p-3">
      <img :src="rawFileUrl(path)" :alt="name" class="max-h-full max-w-full object-contain" />
    </div>
    <div v-if="kind === 'audio' || kind === 'video'" class="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 overflow-auto p-4">
      <audio v-if="kind === 'audio'" :src="rawFileUrl(path)" controls class="w-full max-w-xl" />
      <video v-else :src="rawFileUrl(path)" controls class="max-h-full max-w-full" />
      <a class="btn-secondary" :href="rawFileUrl(path, true)"><AppIcon name="download" />{{ $t('editor.download') }}</a>
    </div>
    <div v-if="kind === 'binary'" class="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <p class="text-slate-300">{{ $t('editor.notText') }}</p>
      <a class="btn-primary" :href="rawFileUrl(path, true)"><AppIcon name="download" />{{ $t('editor.download') }}</a>
    </div>

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
