<script setup lang="ts">
import GpuHoldChips from './GpuHoldChips.vue'

// A view's title with the hold pills beside it, at the far end of the room: the title keeps its full
// width first, the pills take what is left up to their full text, and short of room the title is cut
// only once the pills are down to their dot (GpuHoldChips). The room has no width of its own (like the
// title alone before), so it never pushes the row's buttons into a second line; with a pill it keeps
// at least the dot's.
defineProps<{ titleClass?: string }>()
</script>

<template>
  <div class="flex min-w-0 flex-1 items-center justify-between gap-2 has-[button]:min-w-6">
    <h1 class="min-w-0 truncate font-semibold" :class="titleClass"><slot /></h1>
    <GpuHoldChips />
  </div>
</template>
