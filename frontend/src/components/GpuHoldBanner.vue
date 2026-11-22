<script setup lang="ts">
import { reactive } from 'vue'
import { api } from '../api'
import { useGpuHolds } from '../composables/useGpuHolds'
import { useToast } from '../composables/useToast'
import { type GpuHold, holdView } from '../gpuHolds'

// Somebody (a measurement, a training) asks for or keeps the graphics cards of a machine: shown at
// the top of every page, with the owner, the state and the reason as text (a phone has no
// mouse-over). Only a requested hold can be handed the cards by hand. "Ask for the end" asks the
// owner to stop and let go (a requested hold is withdrawn at once); "Release now" lets go for an
// owner that does not react, so it can only be pressed once the end was asked for. A button that
// cannot be pressed is grayed out with the reason beside it; both changes ask once more in the
// banner itself, saying what follows (a dialog would open beneath the banner). The banner opens by
// itself only while a hand-over can be decided; any other hold shows as a small chip in the page's
// header (GpuHoldChips) right away. "Later" folds the banner to that chip in this browser; a tap on
// it opens the banner again, a new hold shows by its state again.
const toast = useToast()
const { held, refresh, folded, fold } = useGpuHolds()

// One change at a time per hold: while it runs, its buttons are grayed out.
const busy = reactive<Record<string, boolean>>({})
// The change of a hold that was pressed once and waits for the confirmation.
const confirming = reactive<Record<string, 'end' | 'release' | undefined>>({})

async function change(address: string, call: () => Promise<unknown>): Promise<void> {
  busy[address] = true
  try {
    await call()
  } catch (error) {
    toast.error(error)
  } finally {
    busy[address] = false
    confirming[address] = undefined
  }
  await refresh()
}

function grant(address: string, backend: string, owner: string): Promise<void> {
  return change(address, () => api.grantGpuOrcHold(backend, owner))
}

function askEnd(address: string, backend: string, owner: string): Promise<void> {
  return change(address, () => api.askGpuOrcHoldEnd(backend, owner))
}

function release(address: string, backend: string, owner: string): Promise<void> {
  return change(address, () => api.releaseGpuOrcHold(backend, owner))
}

/** What the confirmation says: withdrawing a requested hold differs from asking an active one. */
function confirmKey(address: string, hold: GpuHold): string {
  if (confirming[address] === 'release') return 'gpuHold.releaseConfirm'
  return hold.state === 'requested' ? 'gpuHold.endConfirmRequested' : 'gpuHold.endConfirm'
}
</script>

<template>
  <template v-for="{ address, entry, hold } in held" :key="address">
    <div
      v-if="!folded(address, hold)"
      class="pointer-events-auto flex w-full max-w-xl flex-col gap-2 rounded-lg border border-highlight-500 bg-page px-3 py-2 text-sm shadow-xl"
    >
      <span class="font-semibold text-highlight-200">
        {{ $t('gpuHold.title', { owner: hold.owner, machine: entry.label }) }}
      </span>
      <span class="text-highlight-200">{{ $t(holdView(hold).stateKey, { by: holdView(hold).by, owner: hold.owner }) }}</span>
      <span class="text-main">{{ $t('gpuHold.reason', { reason: hold.reason }) }}</span>
      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="btn-primary btn-small"
          :disabled="!holdView(hold).canGrant || busy[address]"
          @click="grant(address, entry.backend, hold.owner)"
        >
          {{ $t('gpuHold.grant') }}
        </button>
        <span v-if="holdView(hold).blockedKey" class="text-xs text-soft">{{ $t(holdView(hold).blockedKey!) }}</span>
        <button type="button" class="btn-secondary btn-small ml-auto" @click="fold(address, hold, true)">
          {{ $t('gpuHold.later') }}
        </button>
      </div>
      <div v-if="!confirming[address]" class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="btn-danger btn-small"
          :disabled="holdView(hold).endAsked || busy[address]"
          @click="confirming[address] = 'end'"
        >
          {{ $t('gpuHold.end') }}
        </button>
        <span v-if="holdView(hold).endAsked" class="text-xs text-soft">{{ $t('gpuHold.endBlocked') }}</span>
        <button
          type="button"
          class="btn-danger btn-small"
          :disabled="!holdView(hold).endAsked || busy[address]"
          @click="confirming[address] = 'release'"
        >
          {{ $t('gpuHold.release') }}
        </button>
        <span v-if="!holdView(hold).endAsked" class="text-xs text-soft">{{ $t('gpuHold.releaseBlocked', { owner: hold.owner }) }}</span>
      </div>
      <div v-else class="flex flex-wrap items-center gap-2">
        <span class="text-main">{{ $t(confirmKey(address, hold), { owner: hold.owner, machine: entry.label }) }}</span>
        <button
          type="button"
          class="btn-danger btn-small"
          :disabled="busy[address]"
          @click="confirming[address] === 'release' ? release(address, entry.backend, hold.owner) : askEnd(address, entry.backend, hold.owner)"
        >
          {{ $t(confirming[address] === 'release' ? 'gpuHold.releaseNow' : 'gpuHold.endNow') }}
        </button>
        <button type="button" class="btn-secondary btn-small" :disabled="busy[address]" @click="confirming[address] = undefined">
          {{ $t('common.cancel') }}
        </button>
      </div>
    </div>
  </template>
</template>
