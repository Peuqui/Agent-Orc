<script setup lang="ts">
// The name of the workspace shown; typing one and leaving the field names (or renames) it.
defineProps<{ placeholder: string; hint: string }>()
const name = defineModel<string>({ required: true })
const emit = defineEmits<{ rename: [] }>()
</script>

<template>
  <input
    v-model="name"
    size="12"
    class="min-w-0 shrink bg-transparent focus:outline-none"
    :placeholder="placeholder"
    :title="hint"
    :aria-label="hint"
    enterkeyhint="done"
    @keydown.enter="($event.target as HTMLInputElement).blur()"
    @change="emit('rename')"
  />
</template>
