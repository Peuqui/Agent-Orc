<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from '../composables/useToast'
import { useDismiss } from '../composables/useDismiss'
import AppIcon from './AppIcon.vue'

// The paperclip with its menu: take a photo, choose a picture, capture the screen, choose a
// file. The chosen file goes to the parent (`file`), which stores it where it belongs (the
// agent's folder, a note). Its own menu entries and pop-ups go into the slots.
const props = defineProps<{ open: boolean; busy: boolean; extraOpen?: boolean; below?: boolean }>()
const emit = defineEmits<{ toggle: []; close: []; file: [file: File] }>()
const toast = useToast()
const root = ref<HTMLElement>()
const photoInput = ref<HTMLInputElement>()
const imageInput = ref<HTMLInputElement>()
const fileInput = ref<HTMLInputElement>()
// Capturing the screen is a desktop browser feature; phone browsers have none.
const screenCaptureSupported = typeof navigator.mediaDevices?.getDisplayMedia === 'function'
const SCREENSHOT_NAME = 'screenshot.png'
const ITEM_CLASS = 'flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-slate-700'

useDismiss(root, () => props.open || Boolean(props.extraOpen), () => emit('close'))

function choose(input: HTMLInputElement | undefined): void {
  emit('close')
  input?.click()
}

function onFileChosen(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // Cleared, so choosing the same file again still counts as a change.
  input.value = ''
  if (file) emit('file', file)
}

/** The browser asks which screen, window or tab; its current picture is attached. */
async function captureScreen(): Promise<void> {
  emit('close')
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
  if (blob) emit('file', new File([blob], SCREENSHOT_NAME, { type: 'image/png' }))
}
</script>

<template>
  <div ref="root" class="relative">
    <button
      type="button"
      class="btn-icon size-10"
      :class="{ 'animate-pulse': busy }"
      :disabled="busy"
      :aria-label="$t('attach.title')"
      :title="$t('attach.title')"
      @click="emit('toggle')"
    >
      <AppIcon name="paperclip" />
    </button>
    <div
      v-if="open"
      class="card absolute left-0 z-30 flex w-64 flex-col p-1 shadow-xl"
      :class="below ? 'top-full mt-1' : 'bottom-full mb-1'"
    >
      <button type="button" :class="ITEM_CLASS" @click="choose(photoInput)">
        <AppIcon name="camera" />{{ $t('attach.photo') }}
      </button>
      <button type="button" :class="ITEM_CLASS" @click="choose(imageInput)">
        <AppIcon name="image" />{{ $t('attach.image') }}
      </button>
      <button v-if="screenCaptureSupported" type="button" :class="ITEM_CLASS" @click="captureScreen">
        <AppIcon name="screen" />{{ $t('attach.screen') }}
      </button>
      <button type="button" :class="ITEM_CLASS" @click="choose(fileInput)">
        <AppIcon name="paperclip" />{{ $t('attach.file') }}
      </button>
      <slot />
    </div>
    <slot name="popup" />
    <!-- capture opens the camera directly on phones; without it phones offer their gallery
         (newest screenshots first); desktops show the file dialog. -->
    <input ref="photoInput" type="file" accept="image/*" capture="environment" class="hidden" @change="onFileChosen" />
    <input ref="imageInput" type="file" accept="image/*" class="hidden" @change="onFileChosen" />
    <input ref="fileInput" type="file" class="hidden" @change="onFileChosen" />
  </div>
</template>
