<script setup lang="ts">
import { useGpuHolds } from '../composables/useGpuHolds'
import { holdView } from '../gpuHolds'

// The folded holds as small pills in a page's header row: they take their own room there and cover
// nothing. A pill starts as its amber dot (basis-6: padding and dot) and grows into the free room up to
// its full text, before anything else in the row grows: short of room its text is cut from the end,
// the state word first, then the owner. A tap opens the banner with all of it. In the embedded views
// (the workspace's columns) useGpuHolds has no holds: the outermost page shows them, like the banner.
const { held, folded, fold } = useGpuHolds()
</script>

<template>
  <template v-for="{ address, hold } in held" :key="address">
    <button
      v-if="folded(address, hold)"
      type="button"
      data-hold-chip
      class="flex max-w-fit min-w-6 shrink-0 grow-[100] basis-6 items-center gap-1.5 rounded-full bg-highlight-500 px-2 py-0.5 text-xs font-semibold text-on-highlight"
      :aria-label="$t('gpuHold.chip', { owner: hold.owner, state: $t(holdView(hold).stateKey, { by: holdView(hold).by, owner: hold.owner }) })"
      @click="fold(address, hold, false)"
    >
      <span class="size-2 shrink-0 rounded-full bg-on-highlight" :class="{ 'motion-safe:animate-pulse': holdView(hold).decisionOpen }" />
      <span class="min-w-0 truncate">{{ hold.owner }} <span class="font-normal">{{ $t(holdView(hold).shortKey) }}</span></span>
    </button>
  </template>
</template>
