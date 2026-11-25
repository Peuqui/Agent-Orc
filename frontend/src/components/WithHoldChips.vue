<script setup lang="ts">
import GpuHoldChips from './GpuHoldChips.vue'

// What a header row shows first (a title, the logo, the workspace's name) with the hold pills beside
// it, at the far end of the room: the content keeps its full width first, the pills take what is
// left up to their full text, and short of room the content gives way only once the pills are down
// to a small round patch (GpuHoldChips). The room has no width of its own, so it never pushes the
// row's buttons into a second line; with a pill it keeps at least the pill's smallest size.
// minClass: a content that must never be narrower than a button of its own (the workspace's name
// with its arrow) names the room it needs beside the pill; a wrapping row then moves its buttons to
// a second line instead.
withDefaults(defineProps<{ minClass?: string }>(), { minClass: 'min-w-0 has-[[data-hold-chip]]:min-w-5' })
</script>

<template>
  <div class="flex flex-1 items-center justify-between gap-2" :class="minClass">
    <slot />
    <GpuHoldChips />
  </div>
</template>
