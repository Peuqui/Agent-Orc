<script setup lang="ts">
// The speaker symbol of the whole interface: the TTS icon (blue, as in AIfred). `from` adds a small arrow down for
// "reads this answer and the ones after it". `playing`: while it is read, the bars rise and fall like a level and the
// arcs glow, as the dictation's badge does while speech is taken in (DictationBadge.vue). The file is placed in the
// page as it is (its own file, a local asset), so its bars can be moved one by one.
import iconSvg from '../../brand/tts-icon.svg?raw'

defineProps<{ from?: boolean; playing?: boolean }>()
</script>

<template>
  <span class="relative inline-flex size-6 shrink-0">
    <!-- eslint-disable-next-line vue/no-v-html -- the app's own asset, never user text -->
    <span class="icon block size-6" :class="{ playing }" aria-hidden="true" v-html="iconSvg" />
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

<style scoped>
.icon :deep(svg) {
  width: 100%;
  height: 100%;
}
.playing :deep(line) {
  transform-box: fill-box;
  transform-origin: center;
  animation: level 0.9s ease-in-out infinite;
}
.playing :deep(line:nth-child(2)) {
  animation-delay: -0.6s;
}
.playing :deep(line:nth-child(3)) {
  animation-delay: -0.3s;
}
.playing :deep(line:nth-child(4)) {
  animation-delay: -0.75s;
}
.playing :deep(line:nth-child(5)) {
  animation-delay: -0.45s;
}
.playing :deep(path) {
  animation: glow 1.2s ease-in-out infinite;
}
.playing :deep(path:last-child) {
  animation-delay: -0.6s;
}
@media (prefers-reduced-motion: reduce) {
  .playing :deep(line),
  .playing :deep(path) {
    animation: none;
  }
}
@keyframes level {
  0%,
  100% {
    transform: scaleY(0.45);
  }
  50% {
    transform: scaleY(1);
  }
}
@keyframes glow {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}
</style>
