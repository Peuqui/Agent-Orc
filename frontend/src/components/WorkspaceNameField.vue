<script setup lang="ts">
// The name of the workspace shown; typing one and leaving the field names (or renames) it. A
// named workspace can be deleted with the × inside the field. The class goes on the box around
// both, inputClass on the field itself.
defineProps<{ placeholder: string; hint: string; deletable: boolean; inputClass: string }>()
const name = defineModel<string>({ required: true })
const emit = defineEmits<{ rename: []; delete: [] }>()
</script>

<template>
  <span class="relative flex min-w-0 items-center">
    <input
      v-model="name"
      size="12"
      class="min-w-0 flex-1 bg-transparent focus:outline-none"
      :class="[inputClass, deletable ? 'pr-6' : '']"
      :placeholder="placeholder"
      :title="hint"
      :aria-label="hint"
      enterkeyhint="done"
      @keydown.enter="($event.target as HTMLInputElement).blur()"
      @change="emit('rename')"
    />
    <button
      v-if="deletable"
      class="absolute right-1 flex size-5 items-center justify-center rounded text-slate-500 hover:text-slate-200"
      :aria-label="$t('workspace.delete')"
      :title="$t('workspace.delete')"
      @click="emit('delete')"
    >
      ×
    </button>
  </span>
</template>
