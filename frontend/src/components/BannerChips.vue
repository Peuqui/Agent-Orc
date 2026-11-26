<script setup lang="ts">
import { useApprovalFolds } from '../composables/useApprovalFolds'
import { useGpuHolds } from '../composables/useGpuHolds'
import { holdView } from '../gpuHolds'

// The folded cards of the banner as small pills in a page's header row: they take their own room
// there and cover nothing. A pill's colour is the state: red while a decision is open (a request of
// an agent; a hold requested that nobody handed the cards yet; the red of the send button), amber
// otherwise. A pill starts as a small round patch of that colour (basis-5: just its padding, no
// text) and grows into the free room up to its full text, before anything else in the row grows:
// short of room its text is cut from the end, the state word first, then the name. A tap opens the
// card in the banner again. In the embedded views (the workspace's columns) there are no pills: the
// outermost page shows them, like the banner.
const { held, folded, fold } = useGpuHolds()
const approvals = useApprovalFolds()

const PILL = 'flex max-w-fit min-w-5 shrink-0 grow-[100] basis-5 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold'
const DECISION_OPEN = 'bg-accent-600 text-on-color'
</script>

<template>
  <button
    v-for="agent in approvals.foldedAgents.value"
    :key="agent.key"
    type="button"
    data-banner-chip
    :class="[PILL, DECISION_OPEN]"
    :aria-label="$t('approval.chip', { agent: agent.hostName ? `${agent.name} · ${agent.hostName}` : agent.name })"
    @click="approvals.fold(agent.approvalIds, false)"
  >
    <span class="min-w-0 truncate">{{ agent.name }} <span class="font-normal">{{ $t('approval.chipShort') }}</span></span>
  </button>
  <template v-for="{ address, hold } in held" :key="address">
    <button
      v-if="folded(address, hold)"
      type="button"
      data-banner-chip
      :class="[PILL, holdView(hold).decisionOpen ? DECISION_OPEN : 'bg-highlight-500 text-on-highlight']"
      :aria-label="$t('gpuHold.chip', { owner: hold.owner, state: $t(holdView(hold).stateKey, { by: holdView(hold).by, owner: hold.owner }) })"
      @click="fold(address, hold, false)"
    >
      <span class="min-w-0 truncate">{{ hold.owner }} <span class="font-normal">{{ $t(holdView(hold).shortKey) }}</span></span>
    </button>
  </template>
</template>
