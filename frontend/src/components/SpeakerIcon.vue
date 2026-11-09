<script setup lang="ts">
// The speaker symbol of the whole interface: the TTS icon (blue, as in AIfred). `from` adds a small arrow down for
// "reads this answer and the ones after it".
// Imported, so the bundler emits a path that also works under a proxy sub-path.
import iconUrl from '../../brand/tts-icon.svg'

defineProps<{ from?: boolean }>()
</script>

<template>
  <span class="relative inline-flex size-5 shrink-0">
    <img :src="iconUrl" alt="" class="size-5" />
    <svg
      v-if="from"
      class="absolute -right-1 -bottom-1 size-3 rounded-full bg-raised-strong text-main"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="4"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M12 4v15 M6 13l6 6 6-6" />
    </svg>
  </span>
</template>
