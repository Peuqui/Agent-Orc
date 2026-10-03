<script setup lang="ts">
defineProps<{ title: string }>()
const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <div
    class="fixed inset-0 z-40 flex items-end justify-center bg-black/60 sm:items-center"
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
  >
    <div class="card w-full max-w-md rounded-b-none p-5 sm:rounded-b-xl" role="dialog" :aria-label="title">
      <h2 class="mb-4 text-lg font-semibold text-slate-100">{{ title }}</h2>
      <slot />
    </div>
  </div>
</template>
