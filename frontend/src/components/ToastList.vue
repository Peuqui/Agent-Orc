<script setup lang="ts">
import { useToast } from '../composables/useToast'

const { toasts, dismiss } = useToast()
</script>

<template>
  <div class="fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4" aria-live="polite">
    <button
      v-for="toast in toasts"
      :key="toast.id"
      class="w-full max-w-md rounded-lg border px-4 py-3 text-left text-sm shadow-lg"
      :class="
        toast.kind === 'error'
          ? 'border-red-700 bg-red-950 text-red-200'
          : 'border-slate-600 bg-slate-800 text-slate-100'
      "
      @click="dismiss(toast.id)"
    >
      {{ toast.text }}
    </button>
  </div>
</template>
