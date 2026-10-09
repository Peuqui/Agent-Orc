<script setup lang="ts">
import AppIcon from './AppIcon.vue'

// Columns as one boxed group: fewer | count | more, and back to equal widths (dimmed while no
// column has been dragged to another width).
defineProps<{ visible: number; resized: boolean }>()
const emit = defineEmits<{ change: [delta: number]; reset: [] }>()
</script>

<template>
  <div
    class="flex h-8 shrink-0 items-stretch divide-x divide-slate-600 overflow-hidden rounded-md border border-slate-600 text-sm text-slate-300"
    :title="$t('workspace.columns')"
  >
    <button class="w-7 hover:bg-slate-700" :aria-label="$t('workspace.fewerColumns')" @click="emit('change', -1)">−</button>
    <span class="flex w-7 items-center justify-center text-slate-400">{{ visible }}</span>
    <button class="w-7 hover:bg-slate-700" :aria-label="$t('workspace.moreColumns')" @click="emit('change', 1)">+</button>
    <button
      class="flex w-8 items-center justify-center hover:bg-slate-700 disabled:opacity-30 disabled:hover:bg-transparent"
      :disabled="!resized"
      :title="$t('workspace.resetWidths')"
      :aria-label="$t('workspace.resetWidths')"
      @click="emit('reset')"
    >
      <AppIcon name="widths" class="size-4" />
    </button>
  </div>
</template>
