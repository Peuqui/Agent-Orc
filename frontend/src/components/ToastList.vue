<script setup lang="ts">
import { serverReachable } from '../api'
import { useToast } from '../composables/useToast'

const { toasts, dismiss } = useToast()
</script>

<template>
  <div class="fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4" aria-live="polite">
    <p
      v-if="!serverReachable"
      class="w-full max-w-md rounded-lg border border-accent-700 bg-accent-900 px-4 py-3 text-sm text-accent-300 shadow-lg"
    >
      {{ $t('errors.NetworkError') }}
    </p>
    <button
      v-for="toast in toasts"
      :key="toast.id"
      class="w-full max-w-md rounded-lg border px-4 py-3 text-left text-sm shadow-lg"
      :class="
        toast.kind === 'error'
          ? 'border-accent-700 bg-accent-900 text-accent-300'
          : 'border-line-strong bg-panel text-bright'
      "
      @click="dismiss(toast.id)"
    >
      {{ toast.text }}
    </button>
  </div>
</template>
