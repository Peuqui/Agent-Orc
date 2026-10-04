<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useDictation } from '../composables/useDictation'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'

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
    <div v-if="microphone" class="flex flex-col items-center">
      <button
        type="button"
        class="btn-icon min-h-10"
        :class="{ 'animate-pulse text-red-500': microphoneActive, 'opacity-50': microphoneBusy }"
        :disabled="microphoneBusy"
        :aria-label="microphoneActive ? $t('dictation.stop') : $t('dictation.start')"
        :title="microphoneActive ? $t('dictation.stop') : $t('dictation.start')"
        @click="toggleMicrophone"
      >
        <AppIcon name="mic" />
      </button>
      <button
        v-if="whisper"
        type="button"
        class="text-[0.6rem] font-semibold tracking-wide text-slate-400"
        :title="$t('dictation.device')"
        :disabled="state !== 'idle'"
        @click="toggleDevice"
      >
        {{ device === 'cuda' ? 'GPU' : 'CPU' }}
      </button>
    </div>
    <button
      v-if="browserFallback"
      type="button"
      class="btn-secondary min-h-10 px-2 text-xs"
      :class="{ 'animate-pulse text-red-400': state === 'listening' }"
      :disabled="state === 'recording' || state === 'transcribing'"
      :title="$t('dictation.browserHint')"
      @click="toggleBrowser"
    >
      {{ state === 'listening' ? $t('dictation.stop') : $t('dictation.browser') }}
    </button>
    <textarea
      ref="field"
      v-model="text"
      rows="1"
      class="input max-h-[40dvh] min-h-10 flex-1 resize-none py-2"
      :placeholder="state === 'transcribing' ? $t('dictation.transcribing') : $t('terminal.placeholder')"
      enterkeyhint="send"
      @keydown="onKeydown"
    />
    <button type="submit" class="btn-primary min-h-10 px-3" :disabled="!text">
      {{ $t('terminal.send') }}
    </button>
  </form>
</template>
