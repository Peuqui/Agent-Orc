<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { api } from '../api'
import { useGpuHolds } from '../composables/useGpuHolds'
import { useToast } from '../composables/useToast'
import { type GpuHold, holdView, isFolded, setFolded } from '../gpuHolds'

// Somebody (a measurement, a training) asks for or keeps the graphics cards of a machine: shown at
// the top of every page, with the owner, the state and the reason as text (a phone has no
// mouse-over). Only a requested hold can be handed the cards by hand; the button is grayed out
// otherwise, with the reason beside it. "Later" folds the banner to a small notice in this
// browser; a new hold shows in full again.
const toast = useToast()
const { entries, refresh } = useGpuHolds(toast.error)

const held = computed(() =>
  entries.value.flatMap((entry) =>
    entry.hold === null ? [] : [{ address: entry.url ?? entry.backend, entry, hold: entry.hold }],
  ),
)

// Re-read from the storage after a click: it is not reactive.
const foldedVersion = ref(0)
const folded = (address: string, hold: GpuHold): boolean => foldedVersion.value >= 0 && isFolded(address, hold)
function fold(address: string, hold: GpuHold, value: boolean): void {
  setFolded(address, hold, value)
  foldedVersion.value++
}

const granting = reactive<Record<string, boolean>>({})
async function grant(address: string, backend: string, owner: string): Promise<void> {
  granting[address] = true
  try {
    await api.grantGpuOrcHold(backend, owner)
  } catch (error) {
    toast.error(error)
  } finally {
    granting[address] = false
  }
  await refresh()
}
</script>

<template>
  <template v-for="{ address, entry, hold } in held" :key="address">
    <div
      v-if="folded(address, hold)"
      class="pointer-events-auto flex w-full max-w-xl items-center gap-2 rounded-lg border border-highlight-500 bg-page px-3 py-1 text-xs shadow-xl"
    >
      <span class="min-w-0 flex-1 text-highlight-200">
        {{ $t('gpuHold.folded', { owner: hold.owner, state: $t(holdView(hold).stateKey, { by: hold.granted_by }) }) }}
      </span>
      <button type="button" class="btn-secondary btn-small" @click="fold(address, hold, false)">
        {{ $t('gpuHold.unfold') }}
      </button>
    </div>
    <div
      v-else
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
          :disabled="!holdView(hold).canGrant || granting[address]"
          @click="grant(address, entry.backend, hold.owner)"
        >
          {{ $t('gpuHold.grant') }}
        </button>
        <span v-if="holdView(hold).blockedKey" class="text-xs text-soft">{{ $t(holdView(hold).blockedKey!) }}</span>
        <button type="button" class="btn-secondary btn-small ml-auto" @click="fold(address, hold, true)">
          {{ $t('gpuHold.later') }}
        </button>
      </div>
    </div>
  </template>
</template>
