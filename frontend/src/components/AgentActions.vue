<script setup lang="ts">
import { computed } from 'vue'
import type { AgentSession } from '../api'
import { useSessions } from '../composables/useSessions'
import AppIcon from './AppIcon.vue'
import ContextButton from './ContextButton.vue'
import RestartButton from './RestartButton.vue'
import ScheduleButton from './ScheduleButton.vue'

// What is done to a running agent, less often than looking at it (and partly with consequences):
// the content of the ⋮ menu on the card and in the agent's page. The last item stops the agent.
const props = defineProps<{ session: AgentSession }>()
const emit = defineEmits<{ stop: [] }>()
const { profiles } = useSessions()
const itemClass =
  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-700 disabled:opacity-40'
const profile = computed(() => profiles.value.find((p) => p.name === props.session.profile))
</script>

<template>
  <ScheduleButton :session="session" :button-class="itemClass" with-label />
  <RestartButton v-if="profile?.models" change-model :session="session" :button-class="itemClass" with-label />
  <ContextButton
    v-for="action in profile?.context_actions ?? []"
    :key="action"
    :session="session"
    :action="action"
    :button-class="itemClass"
    with-label
  />
  <RestartButton :session="session" :button-class="itemClass" with-label />
  <hr class="my-1 border-slate-700" />
  <button :class="`${itemClass} !text-red-400`" @click="emit('stop')">
    <AppIcon name="stop" />{{ $t('sessions.stop') }}
  </button>
</template>
