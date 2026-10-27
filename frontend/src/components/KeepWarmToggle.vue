<script setup lang="ts">
import { computed } from 'vue'
import type { AgentSession } from '../api'
import { useApi } from '../composables/useHostContext'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'

// Keeping this agent's prompt cache warm: on (amber) or off.
// Compact (a terminal's narrow header, where the agent's name needs the room) it is only a flame.
const props = defineProps<{ session: AgentSession; compact?: boolean }>()
const api = useApi()
const toast = useToast()
const keepWarm = computed(() => props.session.keep_warm)

async function toggle(): Promise<void> {
  const next = !keepWarm.value.enabled
  try {
    await api.setKeepWarm(props.session.id, next)
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <button
    v-if="keepWarm.available"
    type="button"
    class="shrink-0 rounded-full border text-xs whitespace-nowrap"
    :class="[
      compact ? 'p-1' : 'px-2',
      keepWarm.enabled ? 'border-amber-300 text-amber-300' : 'border-slate-600 text-slate-500',
    ]"
    :aria-pressed="keepWarm.enabled"
    :aria-label="$t('keepWarm.label')"
    :title="$t(keepWarm.enabled ? 'keepWarm.onHint' : 'keepWarm.offHint', { count: keepWarm.pings, max: keepWarm.max_pings })"
    @click.stop="toggle"
    @pointerdown.stop
  >
    <AppIcon v-if="compact" name="flame" class="size-4" />
    <template v-else>{{ $t('keepWarm.label') }}</template>
  </button>
</template>
