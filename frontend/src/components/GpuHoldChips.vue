<script setup lang="ts">
import { useGpuHolds } from '../composables/useGpuHolds'
import { holdView } from '../gpuHolds'

// The folded holds as small pills in a page's header row: they take their own room there and cover
// nothing. In the embedded views (the workspace's columns) useGpuHolds has no holds: the outermost
// page shows them, like the banner.
const { held, folded, fold } = useGpuHolds()
</script>

<template>
  <template v-for="{ address, hold } in held" :key="address">
    <button
      v-if="folded(address, hold)"
      type="button"
      class="flex shrink-0 items-center gap-1.5 rounded-full bg-highlight-500 px-2 py-0.5 text-xs font-semibold text-on-highlight"
      :aria-label="$t('gpuHold.chip', { owner: hold.owner, state: $t(holdView(hold).stateKey, { by: hold.granted_by }) })"
      @click="fold(address, hold, false)"
    >
      <span class="size-2 shrink-0 rounded-full bg-on-highlight" :class="{ 'motion-safe:animate-pulse': holdView(hold).pulses }" />
      <span class="max-w-24 truncate">{{ hold.owner }}</span>
      <span class="font-normal">{{ $t(holdView(hold).shortKey) }}</span>
    </button>
  </template>
</template>
