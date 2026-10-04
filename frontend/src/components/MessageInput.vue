<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { api } from '../api'
import { useDictation } from '../composables/useDictation'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ sessionId: string }>()
const emit = defineEmits<{ submit: [text: string] }>()

const toast = useToast()
const text = ref('')
const field = ref<HTMLTextAreaElement>()

const {
  state,
  device,
  whisper,
  microphone,
  browserFallback,
  failedAudio,
  retry,
  toggleDevice,
  toggleMicrophone,
  toggleBrowser,
} = useDictation((dictated) => {
  text.value = text.value ? `${text.value} ${dictated}` : dictated
}, toast.error)

// Without Whisper the microphone itself listens through the browser.
const microphoneActive = computed(
  () => state.value === 'recording' || (whisper.value === false && state.value === 'listening'),
)
const microphoneBusy = computed(
  () => state.value === 'transcribing' || (whisper.value === true && state.value === 'listening'),
)

defineExpose({ focus: () => field.value?.focus() })

// Attaching a photo, screenshot or file: it is stored in the agent's folder, and its path goes
// into the text ("@path", as Claude Code reads files), where the question is added before sending.
const attaching = ref(false)
const uploading = ref(false)
const photoInput = ref<HTMLInputElement>()
const imageInput = ref<HTMLInputElement>()
const fileInput = ref<HTMLInputElement>()
// Capturing the screen is a desktop browser feature; phone browsers have none.
const screenCaptureSupported = typeof navigator.mediaDevices?.getDisplayMedia === 'function'
const SCREENSHOT_NAME = 'screenshot.png'

function choose(input: HTMLInputElement | undefined): void {
  attaching.value = false
  input?.click()
}

async function attachFile(file: File): Promise<void> {
  uploading.value = true
  try {
    const { path } = await api.attach(props.sessionId, file)
    const mention = `@${path} `
    text.value = text.value ? `${text.value} ${mention}` : mention
    field.value?.focus()
  } catch (error) {
    toast.error(error)
  } finally {
    uploading.value = false
  }
}

function onFileChosen(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // Cleared, so choosing the same file again still counts as a change.
  input.value = ''
  if (file) void attachFile(file)
}

/** The browser asks which screen, window or tab; its current picture is attached. */
async function captureScreen(): Promise<void> {
  attaching.value = false
  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
  } catch (error) {
    // The user closed the browser's choice: nothing to attach, nothing to report.
    if (!(error instanceof DOMException && error.name === 'NotAllowedError')) toast.error(error)
    return
  }
  const video = document.createElement('video')
  video.srcObject = stream
  video.muted = true
  await video.play()
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d')?.drawImage(video, 0, 0)
  stream.getTracks().forEach((track) => track.stop())
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (blob) await attachFile(new File([blob], SCREENSHOT_NAME, { type: 'image/png' }))
}

/** A picture pasted into the field (e.g. a screenshot from the clipboard) is attached. */
function onPaste(event: ClipboardEvent): void {
  const images = [...(event.clipboardData?.files ?? [])].filter((file) => file.type.startsWith('image/'))
  if (images.length === 0) return
  event.preventDefault()
  for (const image of images) void attachFile(image)
}

// Grows with its content (up to a cap set in CSS), so a long dictation can be read before sending.
watch(text, async () => {
  await nextTick()
  if (!field.value) return
  field.value.style.height = 'auto'
  field.value.style.height = `${field.value.scrollHeight}px`
})

function submit(): void {
  if (!text.value) return
  emit('submit', text.value)
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
  <form class="flex items-end gap-1 border-t border-slate-800 p-1" @submit.prevent="submit">
    <button
      v-if="failedAudio"
      type="button"
      class="btn-secondary min-h-10 px-1.5 text-xs"
      :disabled="state !== 'idle'"
      :title="$t('dictation.retryHint')"
      @click="retry"
    >
      {{ $t('dictation.retry') }}
    </button>
    <button
      v-if="browserFallback"
      type="button"
      class="btn-secondary min-h-10 px-1.5 text-xs"
      :class="{ 'animate-pulse text-red-400': state === 'listening' }"
      :disabled="state === 'recording' || state === 'transcribing'"
      :title="$t('dictation.browserHint')"
      @click="toggleBrowser"
    >
      {{ state === 'listening' ? $t('dictation.browserStop') : $t('dictation.browser') }}
    </button>
    <div class="relative">
      <button
        type="button"
        class="btn-icon size-10"
        :class="{ 'animate-pulse': uploading }"
        :disabled="uploading"
        :aria-label="$t('attach.title')"
        :title="$t('attach.title')"
        @click="attaching = !attaching"
      >
        <AppIcon name="paperclip" />
      </button>
      <div v-if="attaching" class="card absolute bottom-full left-0 z-30 mb-1 flex w-64 flex-col p-1 shadow-xl">
        <button type="button" class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-slate-700" @click="choose(photoInput)">
          <AppIcon name="camera" />{{ $t('attach.photo') }}
        </button>
        <button type="button" class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-slate-700" @click="choose(imageInput)">
          <AppIcon name="image" />{{ $t('attach.image') }}
        </button>
        <button v-if="screenCaptureSupported" type="button" class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-slate-700" @click="captureScreen">
          <AppIcon name="screen" />{{ $t('attach.screen') }}
        </button>
        <button type="button" class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-slate-700" @click="choose(fileInput)">
          <AppIcon name="paperclip" />{{ $t('attach.file') }}
        </button>
      </div>
      <!-- capture opens the camera directly on phones; without it phones offer their gallery
           (newest screenshots first); desktops show the file dialog. -->
      <input ref="photoInput" type="file" accept="image/*" capture="environment" class="hidden" @change="onFileChosen" />
      <input ref="imageInput" type="file" accept="image/*" class="hidden" @change="onFileChosen" />
      <input ref="fileInput" type="file" class="hidden" @change="onFileChosen" />
    </div>
    <template v-if="microphone">
      <!-- Device switch first and small, the microphone right beside the text field and large:
           the one used most is the easiest to hit. -->
      <button
        v-if="whisper"
        type="button"
        class="mb-2 ml-0.5 h-6 rounded border border-slate-600 px-1 text-[0.6rem] font-semibold tracking-wide text-slate-300 hover:border-slate-400"
        :title="$t('dictation.device')"
        :disabled="state !== 'idle'"
        @click="toggleDevice"
      >
        {{ device === 'cuda' ? 'GPU' : 'CPU' }}
      </button>
      <button
        type="button"
        class="btn-icon size-11"
        :class="[
          microphoneActive ? 'animate-pulse text-red-500' : 'text-amber-300',
          { 'opacity-50': microphoneBusy },
        ]"
        :disabled="microphoneBusy"
        :aria-label="microphoneActive ? $t('dictation.stop') : $t('dictation.start')"
        :title="microphoneActive ? $t('dictation.stop') : $t('dictation.start')"
        @click="toggleMicrophone"
      >
        <AppIcon name="mic" class="size-6" />
      </button>
    </template>
    <textarea
      ref="field"
      v-model="text"
      rows="1"
      class="input max-h-[40dvh] min-h-10 flex-1 resize-none py-2"
      :placeholder="state === 'transcribing' ? $t('dictation.transcribing') : $t('terminal.placeholder')"
      enterkeyhint="send"
      @keydown="onKeydown"
      @paste="onPaste"
    />
    <button
      type="submit"
      class="btn-primary ml-1.5 size-10 px-0"
      :disabled="!text"
      :aria-label="$t('terminal.send')"
      :title="$t('terminal.send')"
    >
      <AppIcon name="send" />
    </button>
  </form>
</template>
