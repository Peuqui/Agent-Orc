<script setup lang="ts">
// top: just below the bar of the button that opened it (e.g. a terminal's bar), instead of a
// sheet from the bottom on narrow screens and centred on wide ones.
defineProps<{ title: string; top?: boolean }>()
const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <div
    class="fixed inset-0 z-40 flex justify-center bg-black/60"
    :class="top ? 'items-start px-2 pt-14' : 'items-end sm:items-center'"
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
  >
    <div
      class="card w-full max-w-md p-5"
      :class="{ 'rounded-b-none sm:rounded-b-xl': !top }"
      role="dialog"
      :aria-label="title"
    >
      <h2 class="mb-4 text-lg font-semibold text-slate-100">{{ title }}</h2>
      <slot />
    </div>
  </div>
</template>
