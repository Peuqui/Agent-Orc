<script setup lang="ts">
import { useGpuHolds } from '../composables/useGpuHolds'
import { holdView } from '../gpuHolds'

// The folded holds as small pills in a page's header row: they take their own room there and cover
// nothing. A pill's colour is the state: red while a decision is open (requested, nobody handed the cards
// yet; the red of the send button), amber otherwise. A pill starts as a small round patch of that
// colour (basis-5: just its padding, no text) and grows into the free room up to its full text,
// before anything else in the row grows: short of room its text is cut from the end, the state word
// first, then the owner. A tap opens the banner with all of it. In the embedded views (the
// workspace's columns) useGpuHolds has no holds: the outermost page shows them, like the banner.
const { held, folded, fold } = useGpuHolds()
</script>

<template>
  <template v-for="{ address, hold } in held" :key="address">
    <button
      v-if="folded(address, hold)"
      type="button"
      data-hold-chip
      class="flex max-w-fit min-w-5 shrink-0 grow-[100] basis-5 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
      :class="holdView(hold).decisionOpen ? 'bg-accent-600 text-on-color' : 'bg-highlight-500 text-on-highlight'"
      :aria-label="$t('gpuHold.chip', { owner: hold.owner, state: $t(holdView(hold).stateKey, { by: holdView(hold).by, owner: hold.owner }) })"
      @click="fold(address, hold, false)"
    >
      <span class="min-w-0 truncate">{{ hold.owner }} <span class="font-normal">{{ $t(holdView(hold).shortKey) }}</span></span>
    </button>
  </template>
</template>
