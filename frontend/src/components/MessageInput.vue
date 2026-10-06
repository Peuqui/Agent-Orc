<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { MESSAGE_FIELD_ATTRIBUTE } from '../columns'
import { useDictation } from '../composables/useDictation'
import { pastedImages } from '../composables/usePastedImages'
import { useToast } from '../composables/useToast'
import { TOUCH_FIRST } from '../device'
import AppIcon from './AppIcon.vue'
import AttachMenu from './AttachMenu.vue'
import DictationMic from './DictationMic.vue'
import DictationRetry from './DictationRetry.vue'
import PromptTemplates from './PromptTemplates.vue'

const props = defineProps<{ sessionId: string }>()
const emit = defineEmits<{ submit: [text: string] }>()

const toast = useToast()
// The unsent text survives a reload (e.g. when a new version is installed), per agent and tab.
const draftKey = `agent-orc-draft:${props.sessionId}`
const text = ref(sessionStorage.getItem(draftKey) ?? '')
watch(text, (current) => {
  if (current) sessionStorage.setItem(draftKey, current)
  else sessionStorage.removeItem(draftKey)
})
const field = ref<HTMLTextAreaElement>()

const dictation = reactive(useDictation(props.sessionId, async (dictated) => {
  text.value = text.value ? `${text.value} ${dictated}` : dictated
  // Ready to send with Enter (or to correct), without clicking into the field first. Not on
  // touch screens: the focus would open the on-screen keyboard; there the send button is ready.
  if (TOUCH_FIRST.matches) return
  await nextTick()
  const input = field.value
  if (!input) return
  input.focus()
  input.setSelectionRange(input.value.length, input.value.length)
}, toast.error))

defineExpose({ focus: () => field.value?.focus() })

// Attaching a photo, screenshot or file: it is stored in the agent's folder, and its path goes
// into the text ("@path", as Claude Code reads files), where the question is added before sending.
const attaching = ref(false)
const uploading = ref(false)
/** An attached file as the user sees it: a small preview for pictures, the name otherwise. */
interface Attachment {
  path: string
  name: string
  preview: string | null
}

// The agent gets the paths ("@path") only when the message is sent; until then the user sees
// previews, not cryptic paths.
const attachments = ref<Attachment[]>([])

async function attachFile(file: File): Promise<void> {
  uploading.value = true
  try {
    const { path } = await api.attach(props.sessionId, file)
    const preview = file.type.startsWith('image/') ? URL.createObjectURL(file) : null
    attachments.value.push({ path, name: file.name, preview })
    field.value?.focus()
  } catch (error) {
    toast.error(error)
  } finally {
    uploading.value = false
  }
}

const templates = ref<InstanceType<typeof PromptTemplates>>()
/** The menu or the template list closes when the user turns elsewhere (AttachMenu). */
function closeMenus(): void {
  attaching.value = false
  if (templates.value) templates.value.open = false
}

/** The paperclip also closes the open template list, which has no button of its own. */
function toggleAttachMenu(): void {
  if (templates.value?.open) {
    templates.value.open = false
    return
  }
  attaching.value = !attaching.value
}

function showTemplates(): void {
  attaching.value = false
  void templates.value?.show()
}

/** A template goes into the field, after what is there already. */
function insertTemplate(template: string): void {
  text.value = text.value ? `${text.value}\n${template}` : template
  field.value?.focus()
}

/**
 * A picture pasted anywhere on the page (e.g. a screenshot from the clipboard) is attached,
 * also while the terminal has the focus; text is pasted as usual.
 */
function onPaste(event: ClipboardEvent): void {
  const images = pastedImages(event)
  if (images.length === 0) return
  // Before the terminal sees it, which would paste nothing useful.
  event.preventDefault()
  event.stopPropagation()
  for (const image of images) void attachFile(image)
}

// Capture phase: the terminal handles pastes into itself and would stop them.
onMounted(() => window.addEventListener('paste', onPaste, true))
onBeforeUnmount(() => window.removeEventListener('paste', onPaste, true))

// Grows with its content (up to a cap set in CSS), so a long dictation can be read before sending.
watch(text, async () => {
  await nextTick()
  if (!field.value) return
  field.value.style.height = 'auto'
  field.value.style.height = `${field.value.scrollHeight}px`
})

function removeAttachment(index: number): void {
  const [removed] = attachments.value.splice(index, 1)
  if (removed?.preview) URL.revokeObjectURL(removed.preview)
}

function clearAttachments(): void {
  for (const attachment of attachments.value) {
    if (attachment.preview) URL.revokeObjectURL(attachment.preview)
  }
  attachments.value = []
}

onBeforeUnmount(clearAttachments)

const sendable = computed(() => text.value !== '' || attachments.value.length > 0)

function submit(): void {
  if (!sendable.value) return
  const mentions = attachments.value.map((attachment) => `@${attachment.path}`)
  emit('submit', [...mentions, text.value].filter((part) => part !== '').join(' '))
  clearAttachments()
  text.value = ''
}

function onKeydown(event: KeyboardEvent): void {
  // Enter sends (also the phone keyboard's send key); Shift+Enter starts a new line.
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="border-t border-slate-800">
  <div v-if="attachments.length" class="flex flex-wrap gap-2 px-2 pt-2">
    <div v-for="(attachment, index) in attachments" :key="attachment.path" class="relative" :title="attachment.name">
      <img
        v-if="attachment.preview"
        :src="attachment.preview"
        :alt="attachment.name"
        class="size-14 rounded-md border border-slate-600 object-cover"
      />
      <div
        v-else
        class="flex h-14 max-w-40 items-center gap-1.5 rounded-md border border-slate-600 bg-slate-800 px-2 text-xs text-slate-300"
      >
        <AppIcon name="file" /><span class="truncate">{{ attachment.name }}</span>
      </div>
      <button
        type="button"
        class="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-slate-900 text-xs text-slate-300 ring-1 ring-slate-600 hover:text-white"
        :aria-label="$t('attach.remove')"
        :title="$t('attach.remove')"
        @click="removeAttachment(index)"
      >
        ×
      </button>
    </div>
  </div>
  <form class="flex items-end gap-1 p-1" @submit.prevent="submit">
    <DictationRetry :dictation="dictation" />
    <AttachMenu
      :open="attaching"
      :extra-open="Boolean(templates?.open)"
      :busy="uploading"
      @toggle="toggleAttachMenu"
      @close="closeMenus"
      @file="attachFile"
    >
      <button type="button" class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-slate-700" @click="showTemplates">
        <AppIcon name="template" />{{ $t('templates.title') }}
      </button>
      <template #popup><PromptTemplates ref="templates" @insert="insertTemplate" /></template>
    </AttachMenu>
    <DictationMic :dictation="dictation" />
    <textarea
      ref="field"
      v-model="text"
      :[MESSAGE_FIELD_ATTRIBUTE]="''"
      rows="1"
      class="input max-h-[40dvh] min-h-10 flex-1 resize-none py-2"
      :placeholder="dictation.state === 'transcribing' ? $t('dictation.transcribing') : $t('terminal.placeholder')"
      enterkeyhint="send"
      @keydown="onKeydown"
    />
    <button
      type="submit"
      class="btn-primary ml-1.5 size-10 px-0"
      :disabled="!sendable"
      :aria-label="$t('terminal.send')"
      :title="$t('terminal.send')"
    >
      <AppIcon name="send" />
    </button>
  </form>
  </div>
</template>
