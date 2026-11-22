<script setup lang="ts">
import { reactive } from 'vue'
import { api } from '../api'
import { useGpuHolds } from '../composables/useGpuHolds'
import { useToast } from '../composables/useToast'
import { holdView } from '../gpuHolds'

// Somebody (a measurement, a training) asks for or keeps the graphics cards of a machine: shown at
// the top of every page, with the owner, the state and the reason as text (a phone has no
// mouse-over). Only a requested hold can be handed the cards by hand; the button is grayed out
// otherwise, with the reason beside it. "End hold" ends any hold, requested or active, after a
// second press in the banner itself that says what follows (a dialog would open beneath the
// banner). The banner opens by itself only while a hand-over can be decided; an effective or
// handed-over hold shows as a small chip in the page's header (GpuHoldChips) right away. "Later" folds the banner to that chip
// in this browser; a tap on it opens the banner again, a new hold shows by its state again.
const toast = useToast()
const { held, refresh, folded, fold } = useGpuHolds()

// One change at a time per hold: while it runs, its buttons are grayed out.
const busy = reactive<Record<string, boolean>>({})
// The holds whose "End hold" was pressed once and waits for the confirmation.
const confirmingEnd = reactive<Record<string, boolean>>({})

async function change(address: string, call: () => Promise<unknown>): Promise<void> {
  busy[address] = true
  try {
    await call()
  } catch (error) {
    toast.error(error)
  } finally {
    busy[address] = false
    confirmingEnd[address] = false
  }
  await refresh()
}

function grant(address: string, backend: string, owner: string): Promise<void> {
  return change(address, () => api.grantGpuOrcHold(backend, owner))
}

function end(address: string, backend: string, owner: string): Promise<void> {
  return change(address, () => api.endGpuOrcHold(backend, owner))
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
      <span class="text-highlight-200">{{ $t(holdView(hold).stateKey, { by: hold.granted_by }) }}</span>
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
        <button
          v-if="!confirmingEnd[address]"
          type="button"
          class="btn-danger btn-small"
          :disabled="busy[address]"
          @click="confirmingEnd[address] = true"
        >
          {{ $t('gpuHold.end') }}
        </button>
        <button type="button" class="btn-secondary btn-small ml-auto" @click="fold(address, hold, true)">
          {{ $t('gpuHold.later') }}
        </button>
      </div>
      <div v-if="confirmingEnd[address]" class="flex flex-wrap items-center gap-2">
        <span class="text-main">{{ $t('gpuHold.endConfirm', { owner: hold.owner, machine: entry.label }) }}</span>
        <button
          type="button"
          class="btn-danger btn-small"
          :disabled="busy[address]"
          @click="end(address, entry.backend, hold.owner)"
        >
          {{ $t('gpuHold.endNow') }}
        </button>
        <button type="button" class="btn-secondary btn-small" :disabled="busy[address]" @click="confirmingEnd[address] = false">
          {{ $t('common.cancel') }}
        </button>
      </div>
    </div>
  </template>
</template>
