<script setup lang="ts">
import { computed } from 'vue'
import { api, type AgentSession } from '../api'
import { useToast } from '../composables/useToast'

// Keeping this agent's prompt cache warm: on (amber) or off. Choosing what the default is leaves the agent
// with the default again, so a later change of the default reaches it.
const props = defineProps<{ session: AgentSession }>()
const toast = useToast()
const keepWarm = computed(() => props.session.keep_warm)

async function toggle(): Promise<void> {
  const next = !keepWarm.value.enabled
  try {
    await api.setKeepWarmAgent(props.session.id, next === keepWarm.value.default ? null : next)
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <button
    v-if="keepWarm.available"
    type="button"
    class="shrink-0 rounded-full border px-2 text-xs whitespace-nowrap"
    :class="keepWarm.enabled ? 'border-amber-300 text-amber-300' : 'border-slate-600 text-slate-500'"
    :aria-pressed="keepWarm.enabled"
    :title="$t(keepWarm.enabled ? 'keepWarm.onHint' : 'keepWarm.offHint', { count: keepWarm.pings })"
    @click.stop="toggle"
    @pointerdown.stop
  >
    {{ $t('keepWarm.label') }}
  </button>
</template>
