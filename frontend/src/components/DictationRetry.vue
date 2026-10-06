<script setup lang="ts">
import type { Dictation } from '../composables/useDictation'

// After Whisper failed: the same recording once more, or the browser's own recognition.
defineProps<{ dictation: Dictation }>()
</script>

<template>
  <button
    v-if="dictation.failedAudio"
    type="button"
    class="btn-secondary min-h-10 px-1.5 text-xs"
    :disabled="dictation.state !== 'idle'"
    :title="$t('dictation.retryHint')"
    @click="dictation.retry"
  >
    {{ $t('dictation.retry') }}
  </button>
  <button
    v-if="dictation.browserFallback"
    type="button"
    class="btn-secondary min-h-10 px-1.5 text-xs"
    :class="{ 'animate-pulse text-red-400': dictation.state === 'listening' }"
    :disabled="dictation.state === 'recording' || dictation.state === 'transcribing'"
    :title="$t('dictation.browserHint')"
    @click="dictation.toggleBrowser"
  >
    {{ dictation.state === 'listening' ? $t('dictation.browserStop') : $t('dictation.browser') }}
  </button>
</template>
