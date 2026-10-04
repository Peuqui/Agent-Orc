<script setup lang="ts">
// An on/off switch with its label in front, e.g. ultracode or notifications.
defineProps<{ checked: boolean }>()
</script>

<template>
  <button type="button" role="switch" class="flex shrink-0 items-center gap-2 disabled:opacity-50" :aria-checked="checked">
    <slot />
    <span class="relative h-4 w-7 rounded-full transition-colors" :class="checked ? 'bg-red-500' : 'bg-slate-600'">
      <span class="absolute top-0.5 size-3 rounded-full bg-white transition-all" :class="checked ? 'left-3.5' : 'left-0.5'" />
    </span>
  </button>
</template>
