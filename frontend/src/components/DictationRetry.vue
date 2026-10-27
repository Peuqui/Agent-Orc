<script setup lang="ts">
import type { Dictation } from '../composables/useDictation'

// After the STT-Suite failed: the same recording once more (on the device chosen now).
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
</template>
