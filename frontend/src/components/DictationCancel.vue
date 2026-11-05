<script setup lang="ts">
import type { Dictation } from '../composables/useDictation'

// On a touch screen, in the place of the paperclip while a dictation is taken in (attaching is of no use then):
// throws the dictation away, as Escape does on a keyboard. In the working colour, which tells it from the red
// microphone beside it.
defineProps<{ dictation: Dictation }>()
</script>

<template>
  <button
    type="button"
    class="btn-icon size-10 text-2xl text-working"
    :aria-label="$t('dictation.cancel')"
    :title="$t('dictation.cancel')"
    @click="dictation.cancel"
  >
    ×
  </button>
</template>
