<script setup lang="ts">
import { MAX_VISIBLE } from '../composables/boundaryShift'
import AppIcon from './AppIcon.vue'

// Columns as one boxed group: fewer | count | more, and back to equal widths (dimmed while no
// column has been dragged to another width).
defineProps<{ visible: number; resized: boolean }>()
const emit = defineEmits<{ change: [delta: number]; reset: [] }>()
</script>

<template>
  <div
    class="flex h-8 shrink-0 items-stretch divide-x divide-line-strong overflow-hidden rounded-md border border-line-strong text-sm text-soft"
    :title="$t('workspace.columns')"
  >
    <button class="w-7 hover:bg-raised" :aria-label="$t('workspace.fewerColumns')" @click="emit('change', -1)">−</button>
    <span class="flex w-7 items-center justify-center text-dim">{{ visible }}</span>
    <button
      class="w-7 hover:bg-raised disabled:opacity-30 disabled:hover:bg-transparent"
      :disabled="visible >= MAX_VISIBLE"
      :aria-label="$t('workspace.moreColumns')"
      @click="emit('change', 1)"
    >
      +
    </button>
    <button
      class="flex w-8 items-center justify-center hover:bg-raised disabled:opacity-30 disabled:hover:bg-transparent"
      :disabled="!resized"
      :title="$t('workspace.resetWidths')"
      :aria-label="$t('workspace.resetWidths')"
      @click="emit('reset')"
    >
      <AppIcon name="widths" class="size-4" />
    </button>
  </div>
</template>
