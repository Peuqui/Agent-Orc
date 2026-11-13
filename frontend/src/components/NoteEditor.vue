<script setup lang="ts">
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { syntaxHighlighting } from '@codemirror/language'
import { languages } from '@codemirror/language-data'
import { Compartment, EditorState } from '@codemirror/state'
import { EditorView, keymap, placeholder } from '@codemirror/view'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCopyText } from '../composables/useCopyText'
import { useSettings } from '../composables/useSettings'
import { useZoomFactor } from '../composables/useViewZoom'
import { codeHighlight, livePreview } from '../livePreview'
import { renderMarkdown } from '../markdown'
import { changeBetween, type Edit } from '../notesFormat'

// The text of a note, edited as it looks (livePreview.ts): Markdown in, Markdown out.
// autofocus: a note without text is there to be written, the cursor goes in.
const props = defineProps<{ modelValue: string; placeholder: string; autofocus: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [text: string]; paste: [event: ClipboardEvent] }>()
const { t } = useI18n()
const copyText = useCopyText()
const { viewFontSize } = useSettings()
// CodeMirror measures where its lines and the cursor are; under the page's zoom it measured wrong.
// So the editor takes the zoom back and is given the views' font size directly (as the file editor).
const { zoomFactor } = useZoomFactor()

const host = ref<HTMLElement>()
const fontTheme = new Compartment()
let view: EditorView | null = null

function fontSizeTheme(size: number) {
  return EditorView.theme({ '&': { fontSize: `${size}px` } })
}

onMounted(() => {
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
        // Enter continues a list or a quote (markdown's own keys); code blocks in their language.
        markdown({ base: markdownLanguage, codeLanguages: languages }),
        syntaxHighlighting(codeHighlight),
        livePreview({
          openLink: (href) => window.open(href, '_blank', 'noopener'),
          copy: (text) => void copyText(text, t('terminal.copied')),
          renderBlock: (text) => renderMarkdown(text, null),
          copyLabel: t('markdown.copyCode'),
        }),
        EditorView.lineWrapping,
        EditorView.contentAttributes.of({ spellcheck: 'false' }),
        placeholder(props.placeholder),
        fontTheme.of(fontSizeTheme(viewFontSize.value)),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) emit('update:modelValue', update.state.doc.toString())
        }),
        EditorView.domEventHandlers({
          paste(event) {
            emit('paste', event)
            return event.defaultPrevented
          },
        }),
      ],
    }),
  })
  if (props.autofocus) view.focus()
})

onBeforeUnmount(() => view?.destroy())

// A change from elsewhere (another device): taken over as one change, the cursor keeps its place.
watch(
  () => props.modelValue,
  (text) => {
    if (view && text !== view.state.doc.toString()) view.dispatch({ changes: changeBetween(view.state.doc.toString(), text) })
  },
)
watch(viewFontSize, (size) => view?.dispatch({ effects: fontTheme.reconfigure(fontSizeTheme(size)) }))

/** Changes the text at the selection (a format, a file link, dictation) and selects what the
 * edit says; `focus` also puts the keyboard there (not for dictation: no keyboard pops up). */
function edit(change: (text: string, from: number, to: number) => Edit, focus: boolean): void {
  if (!view) return
  const text = view.state.doc.toString()
  const { from, to } = view.state.selection.main
  const result = change(text, from, to)
  view.dispatch({
    changes: changeBetween(text, result.text),
    selection: { anchor: result.from, head: result.to },
    scrollIntoView: true,
  })
  if (focus) view.focus()
}

function focus(): void {
  view?.focus()
}

defineExpose({ edit, focus })
</script>

<template>
  <div ref="host" class="note-editor min-w-0" :style="{ zoom: 1 / zoomFactor }" />
</template>
